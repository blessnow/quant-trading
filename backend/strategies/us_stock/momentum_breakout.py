"""动量突破策略 — 美股"""
import numpy as np
import pandas as pd
from loguru import logger

from models import Signal, SignalType, Market, MarketContext
from strategies.base import BaseStrategy
from data.us_stock_provider import get_momentum_stocks, get_stock_history, get_usd_cny_rate


class MomentumBreakout(BaseStrategy):
    """动量突破：20日新高+放量突破，5日最大持有"""

    def get_market(self) -> str:
        return "US_STOCK"

    def get_schedule_config(self) -> dict:
        return {"cron": "45 9 * * mon-fri", "timezone": "America/New_York", "market": "US_STOCK"}

    @classmethod
    def default_params(cls) -> dict:
        return {
            "lookback": 20,
            "top_n": 5,
            "position_pct": 0.15,
            "max_hold_days": 5,
            "trailing_stop_pct": 0.02,
        }

    @classmethod
    def param_space(cls) -> dict:
        return {
            "lookback": [10, 30, 5],
            "top_n": [3, 10, 1],
            "position_pct": [0.05, 0.25, 0.05],
            "trailing_stop_pct": [0.01, 0.05, 0.01],
        }

    def generate_signals(self, context: MarketContext) -> list[Signal]:
        lookback = self.params.get("lookback", 20)
        top_n = self.params.get("top_n", 5)
        pos_pct = self.params.get("position_pct", 0.15)
        trail_stop = self.params.get("trailing_stop_pct", 0.02)

        signals = []

        # 检查现有持仓是否需要止损/止盈
        for pos in context.current_positions:
            if pos.market != Market.US_STOCK:
                continue
            if pos.current_price and pos.avg_cost > 0:
                pnl_pct = (pos.current_price - pos.avg_cost) / pos.avg_cost
                if pnl_pct < -trail_stop:
                    signals.append(Signal(
                        signal_type=SignalType.SELL,
                        symbol=pos.symbol,
                        market=Market.US_STOCK,
                        name=pos.name,
                        price=pos.current_price,
                        shares=pos.shares,
                        confidence=0.8,
                        metadata={"strategy": "MomentumBreakout", "reason": f"止损{pnl_pct:.1%}"},
                    ))

        # 寻找新的动量突破机会
        if context.market == Market.US_STOCK or context.market == "US_STOCK":
            momentum_df = get_momentum_stocks(lookback=lookback)
            if not momentum_df.empty:
                # 筛选接近20日新高的
                breakout = momentum_df[momentum_df["at_20d_high"] == True].head(top_n)
                rate = get_usd_cny_rate()
                for _, row in breakout.iterrows():
                    # 检查是否已持有
                    if any(p.symbol == row["symbol"] for p in context.current_positions):
                        continue

                    budget_usd = context.account_cash / rate * pos_pct
                    shares = int(budget_usd / row["price"])
                    if shares > 0:
                        signals.append(Signal(
                            signal_type=SignalType.BUY,
                            symbol=row["symbol"],
                            market=Market.US_STOCK,
                            name=row["symbol"],
                            price=float(row["price"]),
                            shares=shares,
                            confidence=min(row["momentum_20d"] / 20, 0.95),
                            metadata={
                                "strategy": "MomentumBreakout",
                                "momentum_20d": row["momentum_20d"],
                                "volume_ratio": row["volume_ratio"],
                            },
                        ))

        logger.info(f"[动量突破] 生成 {len(signals)} 个信号")
        return signals
