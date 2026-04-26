"""鱼哥价值投资策略 — LLM Agent ReAct 模式

六步深度研究：股东→公司→财务→行业→产品价格→估值→交易决策
专注资源周期股，长期持有，追求绝对安全边际。
"""
from loguru import logger

from models import Signal, SignalType, Market, MarketContext
from strategies.base import BaseStrategy
from data.a_share_provider import get_industry_board_ranking, get_commodity_prices
from llm.yu_ge_agent import YuGeAgent, yu_ge_set_cached_positions


class YuGeValue(BaseStrategy):
    """鱼哥价值投资策略：LLM ReAct Agent 六步研究"""

    def get_market(self) -> str:
        return "A_SHARE"

    def get_schedule_config(self) -> dict:
        return {"cron": "0 9 * * mon-fri", "timezone": "Asia/Shanghai", "market": "A_SHARE"}

    @classmethod
    def default_params(cls) -> dict:
        return {
            "max_position_pct": 0.70,
            "min_target_upside": 0.30,
            "max_pb": 2.0,
        }

    @classmethod
    def param_space(cls) -> dict:
        return {
            "max_position_pct": [0.30, 0.80, 0.10],
            "min_target_upside": [0.20, 0.50, 0.05],
            "max_pb": [1.0, 3.0, 0.5],
        }

    def generate_signals(self, context: MarketContext) -> list[Signal]:
        # 1. 收集市场基础数据
        market_data = self._collect_market_data()

        # 2. 设置持仓缓存供 Agent 工具查询
        yu_ge_set_cached_positions(context.current_positions)

        # 3. LLM Agent ReAct 推理
        agent = YuGeAgent()
        result = agent.run(market_data, context)

        logger.info(
            f"[鱼哥] LLM决策: action={result.action} "
            f"买入={[t.get('code', '') for t in result.targets]} "
            f"卖出={[s.get('code', '') for s in result.sell_list]}"
        )

        # 保存分析供 scheduler 日志使用
        self._last_analysis = (
            f"操作={result.action} | "
            f"买入={[t.get('code', '') for t in result.targets]} | "
            f"卖出={[s.get('code', '') for s in result.sell_list]} | "
            f"分析: {result.analysis[:300]}"
        )

        # 4. 转换为信号
        signals = self._to_signals(result, context)
        return signals

    def _collect_market_data(self) -> dict:
        from concurrent.futures import ThreadPoolExecutor
        
        data = {
            "策略": "鱼哥价值投资 — 资源周期股深度分析",
            "关注领域": "资源股、周期股、央企国企",
        }

        def fetch_industry():
            try:
                return get_industry_board_ranking()
            except Exception:
                return None
        
        def fetch_commodities():
            try:
                return get_commodity_prices()
            except Exception:
                return None
        
        # 并行获取行业和商品数据
        with ThreadPoolExecutor(max_workers=2) as executor:
            industry_future = executor.submit(fetch_industry)
            commodities_future = executor.submit(fetch_commodities)
            
            industry = industry_future.result()
            commodities = commodities_future.result()

        # 行业板块排名（关注资源类行业）
        if industry is not None and not industry.empty:
            resource_keywords = ["橡胶", "矿产", "有色金属", "煤炭", "钢铁", "石油",
                                 "化工", "黄金", "铜", "铝", "锂", "钼", "稀土",
                                 "种植", "林业", "渔业", "农牧"]
            resource_boards = []
            for _, r in industry.iterrows():
                name = str(r["name"])
                if any(kw in name for kw in resource_keywords):
                    resource_boards.append(
                        f"{name}: 涨跌{r['change_pct']:+.2f}% "
                        f"涨{int(r['up_count'])}/跌{int(r['down_count'])}"
                    )
            if resource_boards:
                data["资源板块行情"] = resource_boards[:10]

        # 大宗商品价格
        if commodities:
            data["大宗商品价格"] = [
                f"{name}: {info.get('price', 'N/A')}" if isinstance(info, dict) else f"{name}: {info}"
                for name, info in commodities.items()
            ]

        return data

    def _to_signals(self, result, context: MarketContext) -> list[Signal]:
        signals = []
        max_pos = self.params.get("max_position_pct", 0.70)

        # 收集所有需要获取价格的股票代码
        sell_codes = [str(s.get("code", "")) for s in result.sell_list]
        buy_codes = [str(t.get("code", "")) for t in result.targets if len(str(t.get("code", ""))) == 6]
        all_codes = list(set(sell_codes + buy_codes))
        
        # 批量获取价格
        from data.a_share_provider import get_batch_prices
        prices = get_batch_prices(all_codes) if all_codes else {}
        logger.info(f"[鱼哥] 批量获取 {len(all_codes)} 只股票价格，成功 {len(prices)} 只")

        # 危出信号
        for s in result.sell_list:
            code = str(s.get("code", ""))
            reason = s.get("reason", "LLM判断卖出")
            for pos in context.current_positions:
                if pos.symbol == code:
                    price = prices.get(code) or pos.current_price or pos.avg_cost
                    signals.append(Signal(
                        signal_type=SignalType.SELL,
                        symbol=code, market=Market.A_SHARE,
                        name=pos.name, price=price, shares=pos.shares,
                        confidence=1.0,
                        metadata={"strategy": "YuGeValue", "reason": reason},
                    ))
                    break

        # 买入信号
        for t in result.targets:
            code = str(t.get("code", ""))
            name = t.get("name", "")
            reason = t.get("reason", "")
            pos_pct = min(float(t.get("position_pct", 0.3)), max_pos)

            if not code or len(code) != 6:
                continue

            price = prices.get(code)
            if not price or price <= 0:
                logger.warning(f"[鱼哥] 无法获取 {code} 价格，跳过")
                continue

            if any(p.symbol == code for p in context.current_positions):
                logger.info(f"[鱼哥] {code} 已持有，跳过")
                continue

            budget = context.account_cash * pos_pct
            shares = int(budget / price // 100) * 100
            if shares < 100:
                logger.warning(f"[鱼哥] {code} 资金不足: 预算{budget:.0f}")
                continue

            signals.append(Signal(
                signal_type=SignalType.BUY,
                symbol=code, market=Market.A_SHARE,
                name=name, price=price, shares=shares,
                confidence=0.9,
                metadata={
                    "strategy": "YuGeValue",
                    "reason": reason,
                    "analysis": result.analysis[:500],
                },
            ))

        return signals
