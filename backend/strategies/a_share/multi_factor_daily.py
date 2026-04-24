"""多因子轮动策略 — 移植自 invest/my/strategy.py"""
import numpy as np
import pandas as pd
from loguru import logger

from models import Signal, SignalType, Market, MarketContext
from strategies.base import BaseStrategy
from data.a_share_provider import get_realtime_quotes, get_stock_history


WEIGHTS = {
    "money_flow": 0.25,
    "smart_money": 0.20,
    "quiet_strength": 0.20,
    "volume_awakening": 0.15,
    "turnover_zone": 0.10,
    "valuation_safety": 0.10,
}


class MultiFactorDaily(BaseStrategy):
    """多因子轮动：每日盘前分析，资金流入+聪明钱+量价背离，周度调仓"""

    def get_market(self) -> str:
        return "A_SHARE"

    def get_schedule_config(self) -> dict:
        return {"cron": "0 9 * * mon-fri", "timezone": "Asia/Shanghai", "market": "A_SHARE"}

    @classmethod
    def default_params(cls) -> dict:
        return {
            "top_n": 5,
            "position_pct": 0.05,
            "rebalance_days": 5,
            "min_price": 5.0,
            "max_price": 100.0,
        }

    @classmethod
    def param_space(cls) -> dict:
        return {
            "top_n": [3, 10, 1],
            "position_pct": [0.03, 0.10, 0.01],
            "rebalance_days": [3, 10, 1],
        }

    def generate_signals(self, context: MarketContext) -> list[Signal]:
        top_n = self.params.get("top_n", 5)
        pos_pct = self.params.get("position_pct", 0.05)

        quotes = get_realtime_quotes()
        if quotes.empty:
            return []

        # 基础过滤
        min_price = self.params.get("min_price", 3)
        max_price = self.params.get("max_price", 200)
        df = quotes[
            (quotes["price"] >= min_price)
            & (quotes["price"] <= max_price)
            & (quotes["change_pct"].abs() < 15)
            & (quotes["volume"] > 0)
            ].copy()

        # 排除ST和北交所
        df = df[~df["name"].str.contains("ST|st", na=False)]
        df = df[~df["code"].astype(str).str.startswith(("8", "4", "688"))]

        if df.empty:
            return []

        # 简化多因子评分（基于行情数据可计算的因子）
        scores = []
        for _, row in df.head(200).iterrows():
            code = str(row["code"])
            hist = get_stock_history(code, days=20)
            if hist.empty or len(hist) < 5:
                continue

            close = hist["close"].values
            vol = hist["volume"].values

            # 动量因子
            mom = (close[-1] - close[-5]) / close[-5] * 100 if len(close) >= 5 else 0

            # 量价配合
            vol_change = (vol[-1] - np.mean(vol[-5:])) / np.mean(vol[-5:]) * 100 if np.mean(vol[-5:]) > 0 else 0

            # 价格位置（相对20日高低）
            high_20 = np.max(close[-20:]) if len(close) >= 20 else np.max(close)
            low_20 = np.min(close[-20:]) if len(close) >= 20 else np.min(close)
            price_pos = (close[-1] - low_20) / (high_20 - low_20) if high_20 > low_20 else 0.5

            score = (
                0.30 * min(max(mom, -10), 10) / 10 * 100
                + 0.25 * min(max(vol_change, -50), 50) / 50 * 100
                + 0.25 * price_pos * 100
                + 0.20 * row["change_pct"]
            )

            scores.append({
                "code": code, "name": row["name"], "price": row["price"],
                "score": round(score, 1), "momentum": round(mom, 2),
            })

        if not scores:
            return []

        score_df = pd.DataFrame(scores).sort_values("score", ascending=False)
        top = score_df.head(top_n)

        signals = []
        for _, row in top.iterrows():
            budget = context.account_cash * pos_pct
            shares = int(budget / row["price"] // 100) * 100
            if shares >= 100:
                signals.append(Signal(
                    signal_type=SignalType.BUY,
                    symbol=str(row["code"]),
                    market=Market.A_SHARE,
                    name=str(row["name"]),
                    price=float(row["price"]),
                    shares=shares,
                    confidence=row["score"] / 100,
                    metadata={"strategy": "MultiFactorDaily", "score": row["score"]},
                ))

        logger.info(f"[多因子] 选出 {len(signals)} 只股票")
        return signals
