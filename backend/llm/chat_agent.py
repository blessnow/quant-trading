"""通用聊天 Agent — 智能投顾对话引擎

支持多策略切换、流式输出、工具调用可视化
"""
import asyncio
import json
import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import AsyncGenerator, Optional

import anthropic
import pandas as pd
from loguru import logger

from data.a_share_provider import (
    get_zt_pool, get_emotion_indicators, get_industry_board_ranking,
    get_realtime_quotes, get_stock_history, get_current_price,
    get_batch_prices, get_stock_fundamentals, get_pb_ratio, get_commodity_prices,
)
from data.market_status import CST
from llm.chat_strategies import get_strategy, ChatStrategy
from llm.prompts import SYSTEM_PROMPT as CHEN_XIAOQUN_SYSTEM
from llm.yu_ge_prompts import SYSTEM_PROMPT as YU_GE_SYSTEM
from llm.general_advisor_prompts import SYSTEM_PROMPT as GENERAL_SYSTEM

MAX_TURNS = 15


def _parallel_fetch(
    items: list,
    fetch_fn,
    max_workers: int = 5,
    timeout: int = 30,
    limit: int = 10
) -> dict:
    """通用的并行获取工具"""
    from concurrent.futures import ThreadPoolExecutor

    results = {}
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(fetch_fn, item) for item in items[:limit]]
        for future in futures:
            try:
                key, data = future.result(timeout=timeout)
                results[key] = data
            except Exception:
                pass
    return results


@dataclass
class ChatMessage:
    """聊天消息"""
    role: str  # user/assistant
    content: str
    tool_calls: list = field(default_factory=list)


@dataclass
class ToolCall:
    """工具调用记录"""
    name: str
    args: dict
    result: str


class ChatAgent:
    """通用聊天 Agent"""

    def __init__(self, strategy_id: str):
        self.strategy_id = strategy_id
        self.strategy = get_strategy(strategy_id)
        if not self.strategy:
            raise ValueError(f"Unknown strategy: {strategy_id}")

        self.client = anthropic.Anthropic(
            base_url=os.environ.get("ANTHROPIC_BASE_URL"),
            api_key=os.environ.get("ANTHROPIC_API_KEY"),
        )
        self.model = os.environ.get("ANTHROPIC_MODEL", "glm-5.1")
        self.system_prompt = self._get_system_prompt()

    def _get_system_prompt(self) -> str:
        """获取策略对应的 System Prompt"""
        prompts = {
            "chen_xiaoqun": CHEN_XIAOQUN_SYSTEM,
            "yu_ge": YU_GE_SYSTEM,
            "general": GENERAL_SYSTEM,
        }
        return prompts.get(self.strategy.system_prompt_key, GENERAL_SYSTEM)

    def _get_tool_definitions(self) -> list:
        """获取策略可用的工具定义"""
        all_tools = {
            "search_web": {
                "name": "search_web",
                "description": "搜索互联网获取最新新闻、政策、板块分析、资金流向等信息。",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "搜索关键词"}
                    },
                    "required": ["query"]
                }
            },
            "get_market_data": {
                "name": "get_market_data",
                "description": "获取A股市场全景数据：涨停池、情绪指标、行业板块排名。",
                "input_schema": {"type": "object", "properties": {}}
            },
            "get_stock_info": {
                "name": "get_stock_info",
                "description": "查询个股详情：实时行情、近20日K线、量价关系等。",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "code": {"type": "string", "description": "6位股票代码"}
                    },
                    "required": ["code"]
                }
            },
            "get_positions": {
                "name": "get_positions",
                "description": "获取当前持仓明细。",
                "input_schema": {"type": "object", "properties": {}}
            },
            "get_stock_fundamentals": {
                "name": "get_stock_fundamentals",
                "description": "获取个股深度基本面数据：公司信息、财务数据、前十大股东。",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "code": {"type": "string", "description": "6位股票代码"}
                    },
                    "required": ["code"]
                }
            },
            "get_pb_ratio": {
                "name": "get_pb_ratio",
                "description": "获取个股估值数据：当前价格、PB、PE、每股净资产。",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "code": {"type": "string", "description": "6位股票代码"}
                    },
                    "required": ["code"]
                }
            },
            "get_commodity_prices": {
                "name": "get_commodity_prices",
                "description": "获取大宗商品价格：黄金、白银、橡胶、铜等。",
                "input_schema": {"type": "object", "properties": {}}
            },
        }

        tools = []
        for tool_name in self.strategy.tools:
            if tool_name in all_tools:
                tools.append(all_tools[tool_name])
        return tools

    async def chat_stream(
        self,
        messages: list[ChatMessage],
        question: str,
        positions: list = None,
    ) -> AsyncGenerator[dict, None]:
        """流式对话，yield SSE 事件"""
        from duckduckgo_search import DDGS

        # 构建消息
        user_prompt = f"当前时间：{datetime.now(CST).strftime('%Y-%m-%d %H:%M')}\n\n用户问题：{question}"
        api_messages = [{"role": "user", "content": user_prompt}]

        # 添加历史消息
        for msg in messages:
            if msg.role == "user":
                api_messages.append({"role": "user", "content": msg.content})
            else:
                api_messages.append({"role": "assistant", "content": msg.content})

        # 缓存持仓数据
        self._cached_positions = positions or []

        tool_definitions = self._get_tool_definitions()
        logger.info(f"[ChatAgent] 开始对话，策略={self.strategy_id}, 模型={self.model}")

        for turn in range(MAX_TURNS):
            try:
                logger.info(f"[ChatAgent] 第{turn+1}轮调用LLM...")
                response = self.client.messages.create(
                    model=self.model,
                    system=self.system_prompt,
                    tools=tool_definitions,
                    messages=api_messages,
                    max_tokens=4096,
                    timeout=1200.0,
                )
                logger.info(f"[ChatAgent] LLM返回 {len(response.content)} 个块")
                await asyncio.sleep(0)  # 让出控制权
            except Exception as e:
                logger.error(f"[ChatAgent] LLM 调用失败: {e}")
                yield {"type": "error", "content": str(e)}
                return

            # 检查工具调用
            tool_use_blocks = [b for b in response.content if b.type == "tool_use"]
            if tool_use_blocks:
                logger.info(f"[ChatAgent] 需要调用 {len(tool_use_blocks)} 个工具: {[b.name for b in tool_use_blocks]}")

                # 合并相同工具的多次调用为批量调用
                merged_calls = self._merge_tool_calls(tool_use_blocks)

                for idx, (merged_name, merged_args, merged_blocks) in enumerate(merged_calls):
                    logger.info(f"[ChatAgent] 工具 {idx+1}/{len(merged_calls)}: {merged_name} ({len(merged_blocks)} 个标的)")

                    # 发送工具调用事件
                    yield {
                        "type": "tool_call",
                        "name": merged_name,
                        "args": merged_args,
                    }
                    await asyncio.sleep(0)  # 让出控制权，确保事件发送

                    # 执行工具
                    try:
                        logger.info(f"[ChatAgent] 开始执行工具: {merged_name}")
                        result = self._execute_tool(merged_name, merged_args, DDGS)
                        logger.info(f"[ChatAgent] 工具 {merged_name} 返回 {len(result)} 字符")
                        yield {
                            "type": "tool_result",
                            "name": merged_name,
                            "result": result[:2000],
                        }
                        await asyncio.sleep(0)  # 让出控制权
                    except Exception as e:
                        logger.error(f"[ChatAgent] 工具 {merged_name} 执行错误: {e}")
                        result = f"工具执行错误: {e}"
                        yield {"type": "tool_result", "name": merged_name, "result": result}

                    # 为每个原始 block 添加结果
                    api_messages.append({"role": "assistant", "content": response.content})
                    for block in merged_blocks:
                        api_messages.append({
                            "role": "user",
                            "content": [{
                                "type": "tool_result",
                                "tool_use_id": block.id,
                                "content": result[:4000],
                            }]
                        })
                
                logger.info(f"[ChatAgent] 所有工具执行完成，进入下一轮")
                await asyncio.sleep(0)
            else:
                # 输出最终回复
                # 处理不同类型的块：text, thinking 等
                text_parts = []
                for b in response.content:
                    if b.type == "text":
                        text_parts.append(b.text)
                    elif b.type == "thinking":
                        # 思考块，跳过或提取 thinking 字段
                        if hasattr(b, 'thinking') and b.thinking:
                            text_parts.append(f"[思考]\n{b.thinking}\n[/思考]\n")
                    # 其他类型忽略
                text = "".join(text_parts)
                if text:
                    logger.info(f"[ChatAgent] 生成回复: {text[:200]}...")
                    yield {"type": "content", "content": text}
                    await asyncio.sleep(0)
                else:
                    logger.warning("[ChatAgent] 无法生成回复")
                    yield {"type": "content", "content": "抱歉，我无法生成回复。"}
                return

        yield {"type": "error", "content": "超过最大思考轮数"}

    def _merge_tool_calls(self, tool_use_blocks) -> list:
        """合并相同工具的多次调用为批量调用"""
        from collections import defaultdict
        
        # 按工具名分组
        groups = defaultdict(list)
        for block in tool_use_blocks:
            groups[block.name].append(block)
        
        merged = []
        for name, blocks in groups.items():
            if name == "get_stock_fundamentals" and len(blocks) > 1:
                codes = [b.input.get("code", "") for b in blocks if b.input.get("code")]
                merged.append(("get_batch_fundamentals", {"codes": codes}, blocks))
            elif name == "get_pb_ratio" and len(blocks) > 1:
                codes = [b.input.get("code", "") for b in blocks if b.input.get("code")]
                merged.append(("get_batch_pb_ratio", {"codes": codes}, blocks))
            elif name == "search_web" and len(blocks) > 1:
                # 合并多个搜索为一个批量搜索
                queries = [b.input.get("query", "") for b in blocks if b.input.get("query")]
                merged.append(("batch_search_web", {"queries": queries}, blocks))
            else:
                for block in blocks:
                    merged.append((name, block.input or {}, [block]))
        
        return merged

    def _execute_tool(self, name: str, args: dict, DDGS) -> str:
        """执行工具"""
        if name == "search_web":
            return self._tool_search_web(args.get("query", ""), DDGS)
        elif name == "batch_search_web":
            return self._tool_batch_search_web(args.get("queries", []), DDGS)
        elif name == "get_market_data":
            return self._tool_get_market_data()
        elif name == "get_stock_info":
            return self._tool_get_stock_info(args.get("code", ""))
        elif name == "get_positions":
            return self._tool_get_positions()
        elif name == "get_stock_fundamentals":
            return self._tool_get_stock_fundamentals(args.get("code", ""))
        elif name == "get_batch_fundamentals":
            return self._tool_get_batch_fundamentals(args.get("codes", []))
        elif name == "get_pb_ratio":
            return self._tool_get_pb_ratio(args.get("code", ""))
        elif name == "get_batch_pb_ratio":
            return self._tool_get_batch_pb_ratio(args.get("codes", []))
        elif name == "get_commodity_prices":
            return self._tool_get_commodity_prices()
        return f"未知工具: {name}"

    def _tool_search_web(self, query: str, DDGS) -> str:
        """搜索网络获取新闻资讯，优先使用 akshare 新闻接口"""
        import akshare as ak
        from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError

        # 提取关键词用于新闻搜索
        keywords = query.replace("A股", "").replace("2026", "").replace("2025", "")
        keywords = keywords.replace("年", "").replace("月", "").replace("日", "")
        keywords = [k.strip() for k in keywords.split() if len(k.strip()) >= 2][:3]

        def search_news():
            results = []
            # 尝试多个关键词搜索
            for keyword in ["股市", "涨停", "A股"]:
                try:
                    news = ak.stock_news_em(symbol=keyword)
                    if not news.empty:
                        for _, row in news.head(5).iterrows():
                            results.append({
                                "title": row.get("新闻标题", ""),
                                "body": row.get("新闻内容", "")[:200],
                                "source": row.get("文章来源", ""),
                                "time": row.get("发布时间", ""),
                            })
                        break
                except Exception:
                    continue
            return results

        try:
            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(search_news)
                results = future.result(timeout=15)

            if not results:
                return f"搜索 '{query}' 无结果，请稍后重试"
            lines = []
            for r in results[:8]:
                lines.append(f"- {r['title']}\n  {r['body']}\n  来源: {r['source']} {r['time']}")
            return "\n\n".join(lines)
        except FuturesTimeoutError:
            return f"搜索 '{query}' 超时，请稍后重试"
        except Exception as e:
            return f"搜索失败: {e}"

    def _tool_batch_search_web(self, queries: list, DDGS) -> str:
        """并行执行多个搜索查询"""
        def search_one(query):
            try:
                return query, self._tool_search_web(query, DDGS)
            except Exception as e:
                return query, f"搜索失败: {e}"

        results = _parallel_fetch(queries, search_one, max_workers=3, timeout=35, limit=5)
        return json.dumps(results, ensure_ascii=False)

    def _tool_get_market_data(self) -> str:
        zt_pool = get_zt_pool()
        emotion = get_emotion_indicators(zt_pool=zt_pool, quotes=None)
        
        try:
            industry = get_industry_board_ranking()
        except Exception as e:
            logger.warning(f"获取行业板块失败: {e}")
            industry = pd.DataFrame()

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
                })

        if not industry.empty:
            for _, r in industry.head(10).iterrows():
                result["industry_top10"].append({
                    "name": str(r["name"]), "change_pct": float(r["change_pct"]),
                    "up_count": int(r["up_count"]), "down_count": int(r["down_count"]),
                })

        return json.dumps(result, ensure_ascii=False)

    def _tool_get_stock_info(self, code: str) -> str:
        code = str(code).strip()
        price = get_current_price(code)
        hist = get_stock_history(code, days=20)

        result = {"code": code, "current_price": price, "history": []}

        if not hist.empty:
            for _, r in hist.tail(20).iterrows():
                result["history"].append({
                    "open": float(r.get("open", 0)) if "open" in r.index else 0,
                    "close": float(r.get("close", 0)) if "close" in r.index else 0,
                    "high": float(r.get("high", 0)) if "high" in r.index else 0,
                    "low": float(r.get("low", 0)) if "low" in r.index else 0,
                    "volume": float(r.get("volume", 0)) if "volume" in r.index else 0,
                })

        return json.dumps(result, ensure_ascii=False)

    def _tool_get_positions(self) -> str:
        if not self._cached_positions:
            return "当前空仓"
        lines = []
        for p in self._cached_positions:
            pnl_pct = 0
            if p.avg_cost > 0 and p.current_price:
                pnl_pct = (p.current_price - p.avg_cost) / p.avg_cost * 100
            lines.append(
                f"{p.symbol} {p.name} {int(p.shares)}股 "
                f"成本{p.avg_cost:.2f} 现价{p.current_price or 0:.2f} "
                f"盈亏{pnl_pct:+.1f}%"
            )
        return "\n".join(lines)

    def _tool_get_stock_fundamentals(self, code: str) -> str:
        code = str(code).strip()
        data = get_stock_fundamentals(code)
        if "financials" in data and isinstance(data["financials"], list):
            data["financials"] = data["financials"][:3]
        return json.dumps(data, ensure_ascii=False, default=str)[:5000]

    def _tool_get_batch_fundamentals(self, codes: list) -> str:
        """并行获取多只股票的基本面数据"""
        def fetch_one(code):
            try:
                data = get_stock_fundamentals(str(code).strip())
                if "financials" in data and isinstance(data["financials"], list):
                    data["financials"] = data["financials"][:2]
                return code, data
            except Exception as e:
                return code, {"error": str(e)}

        results = _parallel_fetch(codes, fetch_one, max_workers=5, limit=10)
        return json.dumps(results, ensure_ascii=False, default=str)[:8000]

    def _tool_get_pb_ratio(self, code: str) -> str:
        code = str(code).strip()
        data = get_pb_ratio(code)
        return json.dumps(data, ensure_ascii=False, default=str)

    def _tool_get_batch_pb_ratio(self, codes: list) -> str:
        """并行获取多只股票的估值数据"""
        def fetch_one(code):
            try:
                return code, get_pb_ratio(str(code).strip())
            except Exception as e:
                return code, {"error": str(e)}

        results = _parallel_fetch(codes, fetch_one, max_workers=5, limit=10)
        return json.dumps(results, ensure_ascii=False, default=str)[:4000]

    def _tool_get_commodity_prices(self) -> str:
        data = get_commodity_prices()
        return json.dumps(data, ensure_ascii=False, default=str)
