"""涨停预判策略 — 移植自 stock/strategy.py"""
import time
from typing import Optional

import numpy as np
import pandas as pd
from loguru import logger

from models import Signal, SignalType, Market, MarketContext
from strategies.base import BaseStrategy
from data.a_share_provider import (
    get_realtime_quotes, get_stock_history, enrich_candidate,
    get_limit_up_codes, is_at_limit,
)


WEIGHTS = {
    "proximity": 0.20,
    "close_strength": 0.20,
    "volume_ratio": 0.12,
    "turnover": 0.08,
    "sector_heat": 0.10,
    "market_cap": 0.05,
    "technical": 0.15,
    "capital_flow": 0.10,
}

MIN_CHANGE_PCT = 7.0
MAX_CHANGE_PCT = 10.5
MIN_CLOSE_HIGH_RATIO = 0.995


class LimitUpPredictor(BaseStrategy):
    """涨停预判策略：14:40扫描接近涨停股，多因子评分选最佳，次日9:35卖出"""

    def get_market(self) -> str:
        return "A_SHARE"

    def get_schedule_config(self) -> dict:
        return {"cron": "40 14 * * mon-fri", "timezone": "Asia/Shanghai", "market": "A_SHARE"}

    @classmethod
    def default_params(cls) -> dict:
        return {
            "min_change_pct": 7.0,
            "max_change_pct": 10.5,
            "max_candidates": 30,
            "position_pct": 0.10,
        }

    @classmethod
    def param_space(cls) -> dict:
        return {
            "min_change_pct": [5.0, 9.0, 0.5],
            "max_candidates": [10, 50, 5],
            "position_pct": [0.05, 0.20, 0.05],
        }

    def generate_signals(self, context: MarketContext) -> list[Signal]:
        min_chg = self.params.get("min_change_pct", MIN_CHANGE_PCT)
        max_chg = self.params.get("max_change_pct", MAX_CHANGE_PCT)
        max_cands = self.params.get("max_candidates", 30)
        pos_pct = self.params.get("position_pct", 0.10)

        quotes = get_realtime_quotes()
        if quotes.empty:
            logger.warning("[涨停预判] 无法获取行情")
            return []

        zt_codes = get_limit_up_codes(quotes)

        # 基础过滤
        candidates = self._pre_filter(quotes, min_chg, max_chg)

        # 逐步放宽
        if candidates.empty:
            candidates = self._pre_filter(quotes, min_chg * 0.7, max_chg)
        if candidates.empty:
            candidates = self._pre_filter(quotes, 3.0, max_chg)
        if candidates.empty:
            logger.warning("[涨停预判] 无候选股")
            return []

        candidates = candidates.head(max_cands)
        scores = self._score_candidates(candidates, zt_codes)

        if scores.empty:
            return []

        best = scores.iloc[0]
        budget = context.account_cash * pos_pct
        shares = int(budget / best["price"] // 100) * 100
        if shares < 100:
            logger.warning(f"[涨停预判] 资金不足: 预算{budget:.0f}, 价格{best['price']}")
            return []

        signal = Signal(
            signal_type=SignalType.BUY,
            symbol=str(best["code"]),
            market=Market.A_SHARE,
            name=str(best["name"]),
            price=float(best["price"]),
            shares=shares,
            confidence=best["total"] / 100,
            metadata={
                "strategy": "LimitUpPredictor",
                "score": round(float(best["total"]), 1),
                "change_pct": float(best["change_pct"]),
            },
        )
        logger.info(f"[涨停预判] 选中 {signal.symbol} {signal.name} 评分={best['total']:.1f}")
        return [signal]

    def _pre_filter(self, df: pd.DataFrame, min_chg: float, max_chg: float) -> pd.DataFrame:
        mask = (
            (df["change_pct"] >= min_chg)
            & (df["change_pct"] <= max_chg)
            & (df["price"] > 0)
        )

        filtered = df[mask].copy()
        # 排除ST和北交所
        filtered = filtered[~filtered["name"].str.contains("ST|st", na=False)]
        filtered = filtered[~filtered["code"].astype(str).str.startswith(("8", "4"))]

        # 排除封死涨停（价格==涨停价，买不进去）
        if "pre_close" in filtered.columns and not filtered.empty:
            not_sealed = filtered.apply(
                lambda r: not is_at_limit(r["price"], r["pre_close"], str(r["code"]), str(r.get("name", ""))),
                axis=1,
            )
            filtered = filtered[not_sealed]

        return filtered.sort_values("change_pct", ascending=False).reset_index(drop=True)

    def _score_candidates(self, candidates: pd.DataFrame, zt_codes: set) -> pd.DataFrame:
        scores = []
        for _, row in candidates.iterrows():
            code = str(row["code"])
            vol = row.get("volume", 0) or 0
            price = row.get("price", 0) or 0
            high = row.get("high", 0) or 0

            extra = enrich_candidate(code, vol)
            hist = get_stock_history(code, days=30)

            s = {
                "code": code, "name": row["name"], "price": price,
                "change_pct": row["change_pct"],
                "total": (
                    WEIGHTS["proximity"] * min(100, (row["change_pct"] / 10) * 100)
                    + WEIGHTS["close_strength"] * self._score_close_strength(price, high)
                    + WEIGHTS["volume_ratio"] * self._score_volume_ratio(extra["volume_ratio"])
                    + WEIGHTS["turnover"] * self._score_turnover(extra["turnover_rate"])
                    + WEIGHTS["sector_heat"] * min(100, sum(1 for c in zt_codes if c.startswith(code[:3])) * 20)
                    + WEIGHTS["market_cap"] * self._score_market_cap(extra["circ_mv_yi"])
                    + WEIGHTS["technical"] * self._score_technical(hist)
                    + WEIGHTS["capital_flow"] * self._score_volume_price(hist)
                ),
            }
            scores.append(s)
            time.sleep(0.03)

        return pd.DataFrame(scores).sort_values("total", ascending=False) if scores else pd.DataFrame()

    @staticmethod
    def _score_close_strength(price, high):
        if high <= 0: return 50.0
        r = price / high
        if r >= 0.995: return 100.0
        if r >= 0.98: return 85.0
        if r >= 0.95: return 50.0
        return 30.0

    @staticmethod
    def _score_volume_ratio(vr):
        if vr < 1.5: return 20.0
        if vr <= 5: return min(100, 40 + (vr - 1.5) / 3.5 * 60)
        if vr <= 8: return 80.0 - (vr - 5) / 3 * 30
        return max(20, 50 - (vr - 8) * 5)

    @staticmethod
    def _score_turnover(tr):
        if tr < 2: return 20.0
        if tr <= 5: return 20 + (tr - 2) / 3 * 40
        if tr <= 15: return 100.0
        return max(20, 100 - (tr - 15) * 5)

    @staticmethod
    def _score_market_cap(mv):
        if mv <= 0: return 60.0
        if mv < 20: return 30.0
        if mv <= 200: return 100.0
        if mv <= 500: return 70.0
        return 40.0

    @staticmethod
    def _score_technical(hist):
        if hist.empty or len(hist) < 10: return 50.0
        close = hist["close"].values
        score = 30.0
        ma5, ma10 = np.mean(close[-5:]), np.mean(close[-10:])
        if ma5 > ma10: score += 12
        if len(close) > 1 and close[-1] > np.max(close[:-1]): score += 15
        return min(100, score)

    @staticmethod
    def _score_volume_price(hist):
        if hist.empty or len(hist) < 5: return 50.0
        vol = hist["volume"].values
        close = hist["close"].values
        score = 40.0
        if vol[-1] == np.max(vol[-5:]): score += 25
        if len(vol) >= 2 and vol[-1] > vol[-2] and close[-1] > close[-2]: score += 20
        return min(100, score)
