"""均值回归策略 — 美股"""
import numpy as np
import pandas as pd
from loguru import logger

from models import Signal, SignalType, Market, MarketContext
from strategies.base import BaseStrategy
from data.us_stock_provider import get_stock_history, DEFAULT_UNIVERSE, get_usd_cny_rate


class MeanReversion(BaseStrategy):
    """均值回归：RSI超卖+Bollinger下轨反弹"""

    def get_market(self) -> str:
        return "US_STOCK"

    def get_schedule_config(self) -> dict:
        return {"cron": "0 12 * * mon-fri", "timezone": "America/New_York", "market": "US_STOCK"}

    @classmethod
    def default_params(cls) -> dict:
        return {
            "rsi_period": 14,
            "rsi_oversold": 30,
            "bb_period": 20,
            "bb_std": 2.0,
            "position_pct": 0.10,
            "max_positions": 3,
            "target_symbols": DEFAULT_UNIVERSE[:30],
        }

    @classmethod
    def param_space(cls) -> dict:
        return {
            "rsi_oversold": [20, 35, 5],
            "bb_std": [1.5, 2.5, 0.5],
            "position_pct": [0.05, 0.15, 0.05],
        }

    def generate_signals(self, context: MarketContext) -> list[Signal]:
        rsi_period = self.params.get("rsi_period", 14)
        rsi_oversold = self.params.get("rsi_oversold", 30)
        bb_period = self.params.get("bb_period", 20)
        bb_std = self.params.get("bb_std", 2.0)
        pos_pct = self.params.get("position_pct", 0.10)
        symbols = self.params.get("target_symbols", DEFAULT_UNIVERSE[:30])

        signals = []

        # 检查持仓是否需要止盈/止损
        for pos in context.current_positions:
            if pos.market != Market.US_STOCK:
                continue
            if pos.current_price and pos.avg_cost > 0:
                pnl_pct = (pos.current_price - pos.avg_cost) / pos.avg_cost
                # 止损 -3% 或 止盈 +5%
                if pnl_pct < -0.03 or pnl_pct > 0.05:
                    signals.append(Signal(
                        signal_type=SignalType.SELL,
                        symbol=pos.symbol,
                        market=Market.US_STOCK,
                        name=pos.name,
                        price=pos.current_price,
                        shares=pos.shares,
                        confidence=0.8,
                        metadata={"strategy": "MeanReversion", "reason": f"{'止盈' if pnl_pct > 0 else '止损'} {pnl_pct:.1%}"},
                    ))

        # 寻找超卖反弹机会
        for sym in symbols:
            if any(p.symbol == sym for p in context.current_positions):
                continue

            hist = get_stock_history(sym, period="3mo")
            if hist.empty or len(hist) < bb_period:
                continue

            close = hist["close"].values

            # 计算RSI
            rsi = self._calc_rsi(close, rsi_period)
            if rsi is None or rsi > rsi_oversold:
                continue

            # 计算Bollinger Band
            sma = np.mean(close[-bb_period:])
            std = np.std(close[-bb_period:])
            lower_band = sma - bb_std * std

            current_price = close[-1]
            # 价格在或低于下轨
            if current_price <= lower_band * 1.01:
                rate = get_usd_cny_rate()
                budget_usd = context.account_cash / rate * pos_pct
                shares = int(budget_usd / current_price)
                if shares > 0:
                    signals.append(Signal(
                        signal_type=SignalType.BUY,
                        symbol=sym,
                        market=Market.US_STOCK,
                        name=sym,
                        price=float(current_price),
                        shares=shares,
                        confidence=min((rsi_oversold - rsi) / rsi_oversold, 0.95),
                        metadata={
                            "strategy": "MeanReversion",
                            "rsi": round(rsi, 1),
                            "bb_lower": round(lower_band, 2),
                        },
                    ))
                    logger.info(f"[均值回归] {sym} RSI={rsi:.1f} BB下轨={lower_band:.2f} 价格={current_price:.2f}")

        return signals

    @staticmethod
    def _calc_rsi(prices, period=14):
        if len(prices) < period + 1:
            return None
        deltas = np.diff(prices[-(period + 1):])
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        avg_gain = np.mean(gains)
        avg_loss = np.mean(losses)
        if avg_loss == 0:
            return 100.0
        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))
