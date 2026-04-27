"""鱼哥价值投资 ReAct Agent — 资源周期股深度基本面分析

通过 LLM + Tool Use 实现 ReAct 循环：
六步研究（股东→公司→财务→行业→产品价格→估值）→ 综合判断 → 交易决策
"""
import json
import os
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

import anthropic
from duckduckgo_search import DDGS
from loguru import logger

from data.a_share_provider import (
    get_stock_fundamentals, get_pb_ratio, get_commodity_prices,
    get_current_price, get_stock_history, get_batch_prices,
    get_realtime_quotes, get_industry_board_ranking,
)
from data.market_status import CST
from llm.yu_ge_prompts import SYSTEM_PROMPT, USER_PROMPT_TEMPLATE

MAX_TURNS = 15


@dataclass
class ValueAgentResult:
    action: str = "hold"
    watchlist_analysis: list = field(default_factory=list)
    targets: list = field(default_factory=list)
    sell_list: list = field(default_factory=list)
    analysis: str = ""
    error: str = ""


class YuGeAgent:
    """LLM ReAct Agent：鱼哥价值投资六步研究"""

    def __init__(self):
        self.client = anthropic.Anthropic(
            base_url=os.environ.get("ANTHROPIC_BASE_URL"),
            api_key=os.environ.get("ANTHROPIC_API_KEY"),
        )
        self.model = os.environ.get("ANTHROPIC_MODEL", "glm-5.1")

    def run(self, market_data: dict, context) -> ValueAgentResult:
        user_prompt = USER_PROMPT_TEMPLATE.format(
            date=datetime.now(CST).strftime("%Y-%m-%d"),
            time=datetime.now(CST).strftime("%H:%M"),
            positions=self._format_positions(context),
            cash=context.account_cash,
            market_data_summary=self._format_market_data(market_data),
        )

        messages = [{"role": "user", "content": user_prompt}]
        logger.info(f"[鱼哥Agent] 开始 ReAct 推理，模型={self.model}")

        for turn in range(MAX_TURNS):
            try:
                response = self.client.messages.create(
                    model=self.model,
                    system=SYSTEM_PROMPT,
                    tools=TOOL_DEFINITIONS,
                    messages=messages,
                    max_tokens=4096,
                    timeout=120.0,
                )
            except Exception as e:
                logger.error(f"[鱼哥Agent] LLM 调用失败: {e}")
                return ValueAgentResult(action="hold", error=str(e))

            tool_use_blocks = [b for b in response.content if b.type == "tool_use"]
            if tool_use_blocks:
                logger.info(f"[鱼哥Agent] 第{turn+1}轮: 调用 {len(tool_use_blocks)} 个工具")
                tool_results = self._execute_tools(tool_use_blocks)
                messages.append({"role": "assistant", "content": response.content})
                messages.append({"role": "user", "content": tool_results})
            else:
                text = "".join(b.text for b in response.content if b.type == "text")
                logger.info(f"[鱼哥Agent] 推理完成，{turn+1}轮")
                return self._parse_decision(text)

        return ValueAgentResult(action="hold", error="超过最大思考轮数")

    def _execute_tools(self, tool_use_blocks) -> list:
        """并行执行多个工具调用"""
        from concurrent.futures import ThreadPoolExecutor, as_completed
        
        results = []
        
        def execute_single_tool(block):
            name = block.name
            args = block.input or {}
            logger.info(f"[鱼哥Agent] 调用 {name}({json.dumps(args, ensure_ascii=False)[:100]})")
            
            try:
                if name == "search_web":
                    output = _tool_search_web(args.get("query", ""))
                elif name == "get_stock_fundamentals":
                    output = _tool_get_stock_fundamentals(args.get("code", ""))
                elif name == "get_batch_fundamentals":
                    output = _tool_get_batch_fundamentals(args.get("codes", []))
                elif name == "get_pb_ratio":
                    output = _tool_get_pb_ratio(args.get("code", ""))
                elif name == "get_batch_pb_ratio":
                    output = _tool_get_batch_pb_ratio(args.get("codes", []))
                elif name == "get_commodity_prices":
                    output = _tool_get_commodity_prices()
                elif name == "get_positions":
                    output = _tool_get_positions()
                else:
                    output = f"未知工具: {name}"
            except Exception as e:
                output = f"工具执行错误: {e}"
                logger.error(f"[鱼哥Agent] {name} 执行失败: {e}")
            
            return {
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": str(output)[:6000],
            }
        
        if len(tool_use_blocks) == 1:
            results.append(execute_single_tool(tool_use_blocks[0]))
        else:
            with ThreadPoolExecutor(max_workers=5) as executor:
                futures = {executor.submit(execute_single_tool, block): block for block in tool_use_blocks}
                for future in as_completed(futures):
                    try:
                        results.append(future.result())
                    except Exception as e:
                        block = futures[future]
                        results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": f"工具执行错误: {e}",
                        })
        
        return results

    def _parse_decision(self, text: str) -> ValueAgentResult:
        json_match = re.search(r"```json\s*(\{.*?\})\s*```", text, re.DOTALL)
        if not json_match:
            json_match = re.search(r"(\{[^{}]*\"action\"[^{}]*\})", text, re.DOTALL)

        if not json_match:
            logger.warning(f"[鱼哥Agent] 无法解析决策 JSON: {text[:200]}")
            return ValueAgentResult(action="hold", analysis=text)

        try:
            data = json.loads(json_match.group(1))
            return ValueAgentResult(
                action=data.get("action", "hold"),
                watchlist_analysis=data.get("watchlist_analysis", []),
                targets=data.get("targets", []),
                sell_list=data.get("sell_list", []),
                analysis=data.get("analysis", text),
            )
        except json.JSONDecodeError as e:
            logger.warning(f"[鱼哥Agent] JSON 解析失败: {e}")
            return ValueAgentResult(action="hold", analysis=text)

    @staticmethod
    def _format_positions(context) -> str:
        if not context.current_positions:
            return "空仓"
        lines = []
        for p in context.current_positions:
            pnl = (p.current_price or p.avg_cost) - p.avg_cost
            pnl_pct = pnl / p.avg_cost * 100 if p.avg_cost > 0 else 0
            lines.append(f"{p.symbol} {p.name} {int(p.shares)}股 成本{p.avg_cost:.2f} 现价{p.current_price or 0:.2f} 盈亏{pnl_pct:+.1f}%")
        return "\n".join(lines)

    @staticmethod
    def _format_market_data(data: dict) -> str:
        lines = []
        for k, v in data.items():
            if isinstance(v, (list, dict)):
                lines.append(f"{k}: {json.dumps(v, ensure_ascii=False)[:500]}")
            else:
                lines.append(f"{k}: {v}")
        return "\n".join(lines)


# ─── 工具定义 ───────────────────────────────────────

TOOL_DEFINITIONS = [
    {
        "name": "search_web",
        "description": "搜索互联网获取最新研报、行业分析、产品价格走势、政策信息等。优先搜索券商研报、东方财富等专业财经来源。",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "搜索关键词，如 '海南橡胶 研报 业绩预期'、'天然橡胶 价格 走势'、'资源股 周期 底部'"
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "get_stock_fundamentals",
        "description": "获取个股深度基本面数据：公司信息（行业、市值、总股本）、最近4期财务数据（净利润、营收、毛利率、ROE、每股净资产等）、前十大股东。这是六步研究的第一到第三步的核心工具。",
        "input_schema": {
            "type": "object",
            "properties": {
                "code": {"type": "string", "description": "6位股票代码，如 601118"}
            },
            "required": ["code"]
        }
    },
    {
        "name": "get_batch_fundamentals",
        "description": "批量获取多只股票的基本面数据，比逐个调用更高效。返回每只股票的公司信息、财务数据摘要。",
        "input_schema": {
            "type": "object",
            "properties": {
                "codes": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "股票代码列表，如 ['601118', '600028']"
                }
            },
            "required": ["codes"]
        }
    },
    {
        "name": "get_pb_ratio",
        "description": "获取个股估值数据：当前价格、PB（市净率）、PE（市盈率）、每股净资产、每股收益。用于第六步估值判断。",
        "input_schema": {
            "type": "object",
            "properties": {
                "code": {"type": "string", "description": "6位股票代码，如 601118"}
            },
            "required": ["code"]
        }
    },
    {
        "name": "get_batch_pb_ratio",
        "description": "批量获取多只股票的估值数据（PB、PE、价格），比逐个调用更高效。",
        "input_schema": {
            "type": "object",
            "properties": {
                "codes": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "股票代码列表，如 ['601118', '600028']"
                }
            },
            "required": ["codes"]
        }
    },
    {
        "name": "get_commodity_prices",
        "description": "获取大宗商品和资源品价格：黄金、白银、橡胶、螺纹钢、铁矿石、铜、铝等。用于第五步产品价格分析。",
        "input_schema": {"type": "object", "properties": {}}
    },
    {
        "name": "get_positions",
        "description": "获取当前策略的所有持仓明细：股票代码、名称、持仓数量、成本价、现价、盈亏比例。",
        "input_schema": {"type": "object", "properties": {}}
    },
]


# ─── 工具实现 ───────────────────────────────────────

def _tool_search_web(query: str) -> str:
    """搜索网络获取新闻资讯，使用 akshare 新闻接口"""
    import akshare as ak

    try:
        # 尝试多个关键词搜索
        results = []
        for keyword in ["股市", "涨停", "A股"]:
            try:
                news = ak.stock_news_em(symbol=keyword)
                if not news.empty:
                    for _, row in news.head(8).iterrows():
                        results.append({
                            "title": row.get("新闻标题", ""),
                            "body": row.get("新闻内容", "")[:200],
                            "source": row.get("文章来源", ""),
                            "time": row.get("发布时间", ""),
                        })
                    break
            except Exception:
                continue

        if not results:
            return f"搜索 '{query}' 无结果"
        lines = []
        for r in results:
            lines.append(f"- {r['title']}\n  {r['body']}\n  来源: {r['source']} {r['time']}")
        return "\n\n".join(lines)
    except Exception as e:
        return f"搜索失败: {e}"


def _tool_get_stock_fundamentals(code: str) -> str:
    code = str(code).strip()
    data = get_stock_fundamentals(code)
    if "financials" in data and isinstance(data["financials"], list):
        data["financials"] = data["financials"][:3]
    return json.dumps(data, ensure_ascii=False, default=str)[:5000]


def _tool_get_batch_fundamentals(codes: list) -> str:
    """并行获取多只股票的基本面数据"""
    from concurrent.futures import ThreadPoolExecutor
    
    def fetch_one(code):
        try:
            data = get_stock_fundamentals(str(code).strip())
            if "financials" in data and isinstance(data["financials"], list):
                data["financials"] = data["financials"][:2]
            return code, data
        except Exception as e:
            return code, {"error": str(e)}
    
    results = {}
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(fetch_one, code): code for code in codes[:10]}
        for future in futures.values():
            try:
                code, data = future.result()
                results[code] = data
            except Exception:
                pass
    
    return json.dumps(results, ensure_ascii=False, default=str)[:8000]


def _tool_get_pb_ratio(code: str) -> str:
    code = str(code).strip()
    data = get_pb_ratio(code)
    return json.dumps(data, ensure_ascii=False, default=str)


def _tool_get_batch_pb_ratio(codes: list) -> str:
    """并行获取多只股票的估值数据"""
    from concurrent.futures import ThreadPoolExecutor
    
    def fetch_one(code):
        try:
            return code, get_pb_ratio(str(code).strip())
        except Exception as e:
            return code, {"error": str(e)}
    
    results = {}
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(fetch_one, code): code for code in codes[:10]}
        for future in futures.values():
            try:
                code, data = future.result()
                results[code] = data
            except Exception:
                pass
    
    return json.dumps(results, ensure_ascii=False, default=str)[:4000]


def _tool_get_commodity_prices() -> str:
    data = get_commodity_prices()
    return json.dumps(data, ensure_ascii=False, default=str)


# 全局持仓缓存
_cached_positions: list = []


def yu_ge_set_cached_positions(positions: list):
    global _cached_positions
    _cached_positions = positions


def _tool_get_positions() -> str:
    if not _cached_positions:
        return "当前空仓"
    lines = []
    for p in _cached_positions:
        pnl_pct = 0
        if p.avg_cost > 0 and p.current_price:
            pnl_pct = (p.current_price - p.avg_cost) / p.avg_cost * 100
        lines.append(
            f"{p.symbol} {p.name} {int(p.shares)}股 "
            f"成本{p.avg_cost:.2f} 现价{p.current_price or 0:.2f} "
            f"盈亏{pnl_pct:+.1f}% 买入日{p.buy_date}"
        )
    return "\n".join(lines)
