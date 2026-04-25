"""ReAct Trading Agent — 陈小群短线决策引擎

通过 LLM + Tool Use 实现 ReAct 循环：
规划(Plan) → 执行(Act) → 观察(Observe) → 决策(Decide)
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
    get_zt_pool, get_emotion_indicators, get_industry_board_ranking,
    get_realtime_quotes, get_stock_history, get_current_price,
    get_batch_prices,
)
from data.market_status import CST
from llm.prompts import SYSTEM_PROMPT, USER_PROMPT_TEMPLATE

MAX_TURNS = 10


@dataclass
class AgentResult:
    action: str = "hold"
    emotion_stage: str = ""
    main_sectors: list = field(default_factory=list)
    targets: list = field(default_factory=list)
    sell_list: list = field(default_factory=list)
    analysis: str = ""
    error: str = ""


class TradingAgent:
    """LLM ReAct Agent：陈小群短线龙头决策"""

    def __init__(self):
        self.client = anthropic.Anthropic(
            base_url=os.environ.get("ANTHROPIC_BASE_URL"),
            api_key=os.environ.get("ANTHROPIC_API_KEY"),
        )
        self.model = os.environ.get("ANTHROPIC_MODEL", "glm-5.1")

    def run(self, market_data: dict, context) -> AgentResult:
        """执行 ReAct 循环，返回结构化交易决策"""
        user_prompt = USER_PROMPT_TEMPLATE.format(
            date=datetime.now(CST).strftime("%Y-%m-%d"),
            time=datetime.now(CST).strftime("%H:%M"),
            positions=self._format_positions(context),
            cash=context.account_cash,
            market_data_summary=self._format_market_data(market_data),
        )

        messages = [{"role": "user", "content": user_prompt}]
        logger.info(f"[Agent] 开始 ReAct 推理，模型={self.model}")

        for turn in range(MAX_TURNS):
            try:
                response = self.client.messages.create(
                    model=self.model,
                    system=SYSTEM_PROMPT,
                    tools=TOOL_DEFINITIONS,
                    messages=messages,
                    max_tokens=4096,
                    timeout=1200.0,
                )
            except Exception as e:
                logger.error(f"[Agent] LLM 调用失败: {e}")
                return AgentResult(action="hold", error=str(e))

            # 检查是否需要执行工具
            tool_use_blocks = [b for b in response.content if b.type == "tool_use"]
            if tool_use_blocks:
                logger.info(f"[Agent] 第{turn+1}轮: 调用 {len(tool_use_blocks)} 个工具")
                tool_results = self._execute_tools(tool_use_blocks)
                messages.append({"role": "assistant", "content": response.content})
                messages.append({"role": "user", "content": tool_results})
            else:
                # LLM 输出最终决策
                text = "".join(b.text for b in response.content if b.type == "text")
                logger.info(f"[Agent] 推理完成，{turn+1}轮")
                return self._parse_decision(text)

        return AgentResult(action="hold", error="超过最大思考轮数")

    def _execute_tools(self, tool_use_blocks) -> list:
        """执行 LLM 请求的工具调用"""
        results = []
        for block in tool_use_blocks:
            name = block.name
            args = block.input or {}
            logger.info(f"[Agent] 调用 {name}({json.dumps(args, ensure_ascii=False)[:100]})")

            try:
                if name == "search_web":
                    output = _tool_search_web(args.get("query", ""))
                elif name == "get_market_data":
                    output = _tool_get_market_data()
                elif name == "get_stock_info":
                    output = _tool_get_stock_info(args.get("code", ""))
                elif name == "get_positions":
                    output = _tool_get_positions()
                else:
                    output = f"未知工具: {name}"
            except Exception as e:
                output = f"工具执行错误: {e}"
                logger.error(f"[Agent] {name} 执行失败: {e}")

            results.append({
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": str(output)[:4000],
            })
        return results

    def _parse_decision(self, text: str) -> AgentResult:
        """从 LLM 输出中提取 JSON 决策"""
        json_match = re.search(r"```json\s*(\{.*?\})\s*```", text, re.DOTALL)
        if not json_match:
            # 尝试直接匹配 JSON
            json_match = re.search(r"(\{[^{}]*\"action\"[^{}]*\})", text, re.DOTALL)

        if not json_match:
            logger.warning(f"[Agent] 无法解析决策 JSON: {text[:200]}")
            return AgentResult(action="hold", analysis=text)

        try:
            data = json.loads(json_match.group(1))
            return AgentResult(
                action=data.get("action", "hold"),
                emotion_stage=data.get("emotion_stage", ""),
                main_sectors=data.get("main_sectors", []),
                targets=data.get("targets", []),
                sell_list=data.get("sell_list", []),
                analysis=data.get("analysis", text),
            )
        except json.JSONDecodeError as e:
            logger.warning(f"[Agent] JSON 解析失败: {e}")
            return AgentResult(action="hold", analysis=text)

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
            if isinstance(v, list):
                lines.append(f"{k}: {json.dumps(v, ensure_ascii=False)[:500]}")
            elif isinstance(v, dict):
                lines.append(f"{k}: {json.dumps(v, ensure_ascii=False)[:500]}")
            else:
                lines.append(f"{k}: {v}")
        return "\n".join(lines)


# ─── 工具定义 ───────────────────────────────────────

TOOL_DEFINITIONS = [
    {
        "name": "search_web",
        "description": "搜索互联网获取最新新闻、政策、板块分析、资金流向等信息。可多次调用不同关键词。优先搜索财联社、东方财富等财经来源。",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "搜索关键词，如 'A股 盘前分析'、'光通信 板块 龙头'、'今日涨停 龙虎榜'"
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "get_market_data",
        "description": "获取A股市场全景数据：涨停池（含连板数、行业、换手率）、情绪指标（情绪阶段、涨停/跌停家数、炸板率）、行业板块排名。",
        "input_schema": {"type": "object", "properties": {}}
    },
    {
        "name": "get_stock_info",
        "description": "查询个股详情：实时行情、近20日K线、量价关系、换手率等。",
        "input_schema": {
            "type": "object",
            "properties": {
                "code": {"type": "string", "description": "6位股票代码，如 002290"}
            },
            "required": ["code"]
        }
    },
    {
        "name": "get_positions",
        "description": "获取当前策略的所有持仓明细：股票代码、名称、持仓数量、成本价、现价、盈亏比例、可卖日期。",
        "input_schema": {"type": "object", "properties": {}}
    },
]


# ─── 工具实现 ───────────────────────────────────────

def _tool_search_web(query: str) -> str:
    """DuckDuckGo 搜索"""
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=8))
        if not results:
            return f"搜索 '{query}' 无结果"
        lines = []
        for r in results:
            lines.append(f"- {r.get('title', '')}\n  {r.get('body', '')[:200]}\n  来源: {r.get('href', '')}")
        return "\n\n".join(lines)
    except Exception as e:
        return f"搜索失败: {e}"


def _tool_get_market_data() -> str:
    """市场全景数据"""
    emotion = get_emotion_indicators()
    zt_pool = get_zt_pool()
    industry = get_industry_board_ranking()

    result = {
        "emotion": emotion,
        "zt_pool_top10": [],
        "industry_top10": [],
    }

    if not zt_pool.empty:
        top = zt_pool.nlargest(10, "consecutive_boards")
        for _, r in top.iterrows():
            result["zt_pool_top10"].append({
                "code": str(r["code"]), "name": str(r["name"]),
                "price": float(r["price"]), "consecutive_boards": int(r["consecutive_boards"]),
                "turnover": float(r["turnover"]), "industry": str(r["industry"]),
                "bomb_count": int(r.get("bomb_count", 0)),
            })

    if not industry.empty:
        for _, r in industry.head(10).iterrows():
            result["industry_top10"].append({
                "name": str(r["name"]), "change_pct": float(r["change_pct"]),
                "up_count": int(r["up_count"]), "down_count": int(r["down_count"]),
                "leading_stock": str(r.get("leading_stock", "")),
            })

    return json.dumps(result, ensure_ascii=False)


def _tool_get_stock_info(code: str) -> str:
    """个股详情"""
    code = str(code).strip()
    price = get_current_price(code)
    hist = get_stock_history(code, days=20)

    result = {"code": code, "current_price": price, "history": []}

    if not hist.empty:
        for _, r in hist.tail(20).iterrows():
            row_data = {
                "open": float(r.get("open", 0)) if "open" in r.index else 0,
                "close": float(r.get("close", 0)) if "close" in r.index else 0,
                "high": float(r.get("high", 0)) if "high" in r.index else 0,
                "low": float(r.get("low", 0)) if "low" in r.index else 0,
                "volume": float(r.get("volume", 0)) if "volume" in r.index else 0,
            }
            result["history"].append(row_data)

    return json.dumps(result, ensure_ascii=False)


# 全局持仓缓存，由策略在调用前设置
_cached_positions: list = []


def set_cached_positions(positions: list):
    global _cached_positions
    _cached_positions = positions


def _tool_get_positions() -> str:
    """当前持仓"""
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
            f"盈亏{pnl_pct:+.1f}% 买入日{p.buy_date} 可卖日{p.sellable_date}"
        )
    return "\n".join(lines)
