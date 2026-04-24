"""事件套利策略 — 基于LLM新闻分析"""
from loguru import logger

from models import Signal, SignalType, Market, MarketContext
from strategies.base import BaseStrategy


class EventArbitrage(BaseStrategy):
    """事件套利：盘中监控新闻事件，LLM分析影响，生成交易信号"""

    def get_market(self) -> str:
        return "A_SHARE"

    def get_schedule_config(self) -> dict:
        return {"cron": "*/30 9-14 * * mon-fri", "timezone": "Asia/Shanghai", "market": "A_SHARE"}

    @classmethod
    def default_params(cls) -> dict:
        return {
            "confidence_threshold": 0.7,
            "position_pct": 0.08,
            "max_positions": 3,
        }

    def generate_signals(self, context: MarketContext) -> list[Signal]:
        # 事件套利需要新闻数据源和LLM接口
        # 简化实现：扫描已有持仓，检查是否需要止损
        signals = []
        for pos in context.current_positions:
            if pos.market != Market.A_SHARE:
                continue
            if pos.unrealized_pnl_pct < -0.05:
                signals.append(Signal(
                    signal_type=SignalType.SELL,
                    symbol=pos.symbol,
                    market=Market.A_SHARE,
                    name=pos.name,
                    price=pos.current_price or pos.avg_cost,
                    shares=pos.shares,
                    confidence=0.9,
                    metadata={"strategy": "EventArbitrage", "reason": "止损"},
                ))
                logger.info(f"[事件套利] 止损信号: {pos.symbol} {pos.name} 亏损{pos.unrealized_pnl_pct:.1%}")

        return signals
