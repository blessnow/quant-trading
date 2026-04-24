"""跳空扫描策略 — 美股"""
from loguru import logger

from models import Signal, SignalType, Market, MarketContext
from strategies.base import BaseStrategy
from data.us_stock_provider import get_gap_stocks, get_usd_cny_rate


class GapScanner(BaseStrategy):
    """跳空扫描：隔夜跳空>3%的回补交易"""

    def get_market(self) -> str:
        return "US_STOCK"

    def get_schedule_config(self) -> dict:
        return {"cron": "35 9 * * mon-fri", "timezone": "America/New_York", "market": "US_STOCK"}

    @classmethod
    def default_params(cls) -> dict:
        return {
            "min_gap_pct": 3.0,
            "max_positions": 2,
            "position_pct": 0.12,
        }

    @classmethod
    def param_space(cls) -> dict:
        return {
            "min_gap_pct": [2.0, 5.0, 0.5],
            "position_pct": [0.05, 0.20, 0.05],
        }

    def generate_signals(self, context: MarketContext) -> list[Signal]:
        min_gap = self.params.get("min_gap_pct", 3.0)
        max_pos = self.params.get("max_positions", 2)
        pos_pct = self.params.get("position_pct", 0.12)

        signals = []

        # 检查持仓是否需要平仓
        for pos in context.current_positions:
            if pos.market != Market.US_STOCK:
                continue
            # 跳空策略日内了结
            if pos.current_price and pos.avg_cost > 0:
                pnl_pct = (pos.current_price - pos.avg_cost) / pos.avg_cost
                if pnl_pct > 0.02 or pnl_pct < -0.02:
                    signals.append(Signal(
                        signal_type=SignalType.SELL,
                        symbol=pos.symbol,
                        market=Market.US_STOCK,
                        name=pos.name,
                        price=pos.current_price,
                        shares=pos.shares,
                        confidence=0.8,
                        metadata={"strategy": "GapScanner", "reason": f"日内平仓 {pnl_pct:.1%}"},
                    ))

        # 当前持仓数（排除即将平仓的）
        current_count = sum(1 for p in context.current_positions if p.market == Market.US_STOCK)

        if current_count >= max_pos:
            return signals

        # 扫描跳空
        gap_df = get_gap_stocks(min_gap_pct=min_gap)
        if gap_df.empty:
            logger.info("[跳空扫描] 未发现符合条件的跳空股")
            return signals

        rate = get_usd_cny_rate()
        slots = max_pos - current_count

        for _, row in gap_df.head(slots).iterrows():
            budget_usd = context.account_cash / rate * pos_pct
            shares = int(budget_usd / row["price"])
            if shares <= 0:
                continue

            # 跳空向下 → 买入预期回补
            # 跳空向上 → 卖空预期回落（模拟盘暂不支持做空标记）
            if row["gap_pct"] < 0:
                signals.append(Signal(
                    signal_type=SignalType.BUY,
                    symbol=row["symbol"],
                    market=Market.US_STOCK,
                    name=row["symbol"],
                    price=float(row["price"]),
                    shares=shares,
                    confidence=min(abs(row["gap_pct"]) / 10, 0.9),
                    metadata={
                        "strategy": "GapScanner",
                        "gap_pct": row["gap_pct"],
                        "reason": f"跳空下行{row['gap_pct']:.1f}%，预期回补",
                    },
                ))
                logger.info(f"[跳空扫描] {row['symbol']} 跳空{row['gap_pct']:.1f}% → 买入")

        return signals
