"""陈小群短线龙头策略 — LLM Agent ReAct 模式

决策流程：LLM 自主规划 → 调工具搜索/查询 → 推理分析 → 输出交易决策
不使用任何硬编码规则，所有判断由 LLM 基于「陈小群框架」完成。
"""
from loguru import logger

from models import Signal, SignalType, Market, MarketContext
from strategies.base import BaseStrategy
from data.a_share_provider import get_emotion_indicators, get_zt_pool
from llm.agent import TradingAgent, set_cached_positions


class ChenXiaoqunShort(BaseStrategy):
    """陈小群短线龙头策略：LLM ReAct Agent 决策"""

    def get_market(self) -> str:
        return "A_SHARE"

    def get_schedule_config(self) -> dict:
        return {"cron": "0 9 * * mon-fri", "timezone": "Asia/Shanghai", "market": "A_SHARE"}

    @classmethod
    def default_params(cls) -> dict:
        return {
            "max_position_pct": 0.30,
            "stop_loss_pct": 0.05,
            "max_price": 50.0,
        }

    @classmethod
    def param_space(cls) -> dict:
        return {
            "max_position_pct": [0.10, 0.40, 0.05],
            "stop_loss_pct": [0.03, 0.08, 0.01],
            "max_price": [30.0, 80.0, 10.0],
        }

    def generate_signals(self, context: MarketContext) -> list[Signal]:
        # 1. 收集市场基础数据
        market_data = self._collect_market_data()

        # 2. 设置持仓缓存供 Agent 工具查询
        set_cached_positions(context.current_positions)

        # 3. LLM Agent ReAct 推理
        agent = TradingAgent()
        result = agent.run(market_data, context)

        logger.info(
            f"[陈小群] LLM决策: action={result.action} "
            f"情绪={result.emotion_stage} "
            f"主线={result.main_sectors} "
            f"买入={[t.get('code','') for t in result.targets]} "
            f"卖出={[s.get('code','') for s in result.sell_list]}"
        )

        # 保存分析供 scheduler 日志使用
        self._last_analysis = (
            f"情绪={result.emotion_stage} | "
            f"主线={result.main_sectors} | "
            f"操作={result.action} | "
            f"分析: {result.analysis[:300]}"
        )

        # 4. 转换为信号
        signals = self._to_signals(result, context)
        return signals

    def _collect_market_data(self) -> dict:
        """收集市场基础数据传给 LLM"""
        emotion = get_emotion_indicators()
        zt_pool = get_zt_pool()

        data = {
            "情绪指标": emotion,
            "涨停数量": emotion.get("zt_count", 0),
            "跌停数量": emotion.get("dt_count", 0),
            "最高连板": emotion.get("max_boards", 0),
            "炸板率": f"{emotion.get('bomb_rate', 0)}%",
            "情绪阶段": emotion.get("stage", "未知"),
        }

        if not zt_pool.empty:
            top_boards = zt_pool.nlargest(5, "consecutive_boards")
            data["连板前排"] = [
                f"{r['code']} {r['name']} {int(r['consecutive_boards'])}板 "
                f"换手{r['turnover']:.1f}% 行业={r['industry']}"
                for _, r in top_boards.iterrows()
            ]

            industry_count = zt_pool.groupby("industry").size().sort_values(ascending=False)
            data["行业涨停分布"] = [
                f"{ind}: {cnt}家涨停"
                for ind, cnt in industry_count.head(5).items()
            ]

        return data

    def _to_signals(self, result, context: MarketContext) -> list[Signal]:
        """将 Agent 决策转换为交易信号"""
        signals = []
        max_pos = self.params.get("max_position_pct", 0.30)
        max_price = self.params.get("max_price", 50.0)

        # 退潮空仓：卖出所有持仓
        if result.action == "empty":
            from data.a_share_provider import get_batch_prices
            codes = [p.symbol for p in context.current_positions if p.market == Market.A_SHARE]
            fresh_prices = get_batch_prices(codes) if codes else {}
            for pos in context.current_positions:
                if pos.market == Market.A_SHARE:
                    price = fresh_prices.get(pos.symbol) or pos.current_price or pos.avg_cost
                    signals.append(Signal(
                        signal_type=SignalType.SELL,
                        symbol=pos.symbol, market=Market.A_SHARE,
                        name=pos.name, price=price, shares=pos.shares,
                        confidence=1.0,
                        metadata={"strategy": "ChenXiaoqunShort", "reason": "退潮期空仓"},
                    ))
            return signals

        # 卖出信号
        for s in result.sell_list:
            code = str(s.get("code", ""))
            reason = s.get("reason", "LLM判断卖出")
            for pos in context.current_positions:
                if pos.symbol == code:
                    from data.a_share_provider import get_current_price as _get_price
                    price = _get_price(code) or pos.current_price or pos.avg_cost
                    signals.append(Signal(
                        signal_type=SignalType.SELL,
                        symbol=code, market=Market.A_SHARE,
                        name=pos.name, price=price, shares=pos.shares,
                        confidence=1.0,
                        metadata={"strategy": "ChenXiaoqunShort", "reason": reason},
                    ))
                    break

        # 买入信号
        for t in result.targets:
            code = str(t.get("code", ""))
            name = t.get("name", "")
            reason = t.get("reason", "")
            pos_pct = min(float(t.get("position_pct", 0.1)), max_pos)

            if not code or len(code) != 6:
                continue

            # 获取实时价格
            from data.a_share_provider import get_current_price
            price = get_current_price(code)
            if not price or price <= 0:
                logger.warning(f"[陈小群] 无法获取 {code} 价格，跳过")
                continue

            if price > max_price:
                logger.info(f"[陈小群] {code} 价格{price}超过{max_price}，跳过（低价股优先）")
                continue

            # 已持有的不重复买
            if any(p.symbol == code for p in context.current_positions):
                continue

            budget = context.account_cash * pos_pct
            shares = int(budget / price // 100) * 100
            if shares < 100:
                logger.warning(f"[陈小群] {code} 资金不足: 预算{budget:.0f}")
                continue

            signals.append(Signal(
                signal_type=SignalType.BUY,
                symbol=code, market=Market.A_SHARE,
                name=name, price=price, shares=shares,
                confidence=0.8,
                metadata={
                    "strategy": "ChenXiaoqunShort",
                    "reason": reason,
                    "emotion_stage": result.emotion_stage,
                    "main_sectors": result.main_sectors,
                    "analysis": result.analysis[:500],
                },
            ))

        return signals
