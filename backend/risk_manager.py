"""风控引擎 — 三级风控体系"""
from datetime import datetime
from typing import Optional

from loguru import logger

import config
from database import get_db
from models import Signal, SignalType, Market, MarketContext


class RiskDecision:
    def __init__(self, allowed: bool, reason: str = "", adjusted_shares: float = 0):
        self.allowed = allowed
        self.reason = reason
        self.adjusted_shares = adjusted_shares

    def __bool__(self):
        return self.allowed


class RiskManager:

    async def pre_check(self, strategy_id: int, context: MarketContext) -> RiskDecision:
        """策略级预检：是否允许该策略运行"""
        db = await get_db()
        try:
            # 1. 组合级回撤检查
            async with db.execute("SELECT market FROM accounts") as cur:
                pass

            for market in ["A_SHARE", "US_STOCK"]:
                async with db.execute(
                    """SELECT total_value FROM equity_snapshots
                       WHERE market=? ORDER BY snapshot_date DESC, snapshot_time DESC LIMIT 1""",
                    (market,)
                ) as cur:
                    row = await cur.fetchone()
                if row:
                    async with db.execute("SELECT initial_capital FROM accounts WHERE market=?", (market,)) as cur2:
                        init_row = await cur2.fetchone()
                    if init_row:
                        peak = row[0]
                        initial = init_row[0]
                        # 简化：用初始资金作为峰值基准
                        if initial > 0:
                            drawdown = (initial - peak) / initial
                            if drawdown > config.RISK_PORTFOLIO_DRAWDOWN_LIMIT:
                                await self._log_risk_event("PORTFOLIO_HALT", strategy_id,
                                                           f"{market}组合回撤{drawdown:.1%}超限，暂停交易")
                                return RiskDecision(False, f"{market}组合回撤超限{drawdown:.1%}")

            # 2. 策略级连续亏损检查
            async with db.execute(
                """SELECT side, pnl FROM trades WHERE strategy_id=? AND pnl IS NOT NULL
                   ORDER BY executed_at DESC LIMIT ?""",
                (strategy_id, config.RISK_MAX_CONSECUTIVE_LOSSES)
            ) as cur:
                rows = await cur.fetchall()
            if rows:
                consecutive_losses = 0
                for r in rows:
                    if r[0] == "SELL" and r[1] is not None and r[1] < 0:
                        consecutive_losses += 1
                    else:
                        break
                if consecutive_losses >= config.RISK_MAX_CONSECUTIVE_LOSSES:
                    await self._log_risk_event("STRATEGY_HALT", strategy_id,
                                               f"连续亏损{consecutive_losses}次，暂停1天")
                    return RiskDecision(False, f"连续亏损{consecutive_losses}次")

            # 3. 持仓数量限制
            async with db.execute("SELECT COUNT(*) FROM positions") as cur:
                row = await cur.fetchone()
            if row and row[0] >= config.RISK_MAX_POSITIONS:
                await self._log_risk_event("POSITION_LIMIT", strategy_id,
                                           f"持仓数{row[0]}达上限{config.RISK_MAX_POSITIONS}")
                return RiskDecision(False, f"持仓数已达上限{config.RISK_MAX_POSITIONS}")

            return RiskDecision(True)
        finally:
            await db.close()

    async def validate_signal(self, signal: Signal, context: MarketContext) -> RiskDecision:
        """信号级校验：是否允许这笔交易"""
        db = await get_db()
        try:
            if signal.signal_type == SignalType.BUY:
                # 仓位占比检查
                market = signal.market.value if isinstance(signal.market, Market) else signal.market
                async with db.execute("SELECT cash, initial_capital FROM accounts WHERE market=?", (market,)) as cur:
                    row = await cur.fetchone()
                if not row:
                    return RiskDecision(False, "账户不存在")

                cash, total = row
                position_value = signal.price * signal.shares
                max_allowed = total * config.RISK_MAX_POSITION_PCT

                if position_value > max_allowed:
                    adjusted = int(max_allowed / signal.price)
                    if signal.market == Market.A_SHARE:
                        adjusted = (adjusted // 100) * 100
                    if adjusted <= 0:
                        return RiskDecision(False, f"单仓位超限，调整后为0")
                    logger.info(f"[风控] 仓位调整: {signal.shares} → {adjusted}")
                    return RiskDecision(True, f"仓位调整{signal.shares}→{adjusted}", adjusted)

                # 最低现金储备检查
                if cash - position_value < total * config.RISK_MIN_CASH_RESERVE:
                    available = cash - total * config.RISK_MIN_CASH_RESERVE
                    if available <= 0:
                        return RiskDecision(False, "现金储备不足")
                    adjusted = int(available / signal.price)
                    if signal.market == Market.A_SHARE:
                        adjusted = (adjusted // 100) * 100
                    return RiskDecision(True, "受现金储备限制调整", max(0, adjusted))

                return RiskDecision(True, "", signal.shares)

            return RiskDecision(True, "", signal.shares)
        finally:
            await db.close()

    async def post_check(self, strategy_id: int, trades: list):
        """交易后检查：更新绩效统计"""
        if not trades:
            return
        db = await get_db()
        try:
            # 统计策略绩效
            async with db.execute(
                """SELECT COUNT(*), SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END), COALESCE(SUM(pnl), 0)
                   FROM trades WHERE strategy_id=? AND side='SELL'""",
                (strategy_id,)
            ) as cur:
                row = await cur.fetchone()
            if row:
                total, wins, pnl = row
                total = total or 0
                wins = wins or 0
                win_rate = wins / total if total > 0 else 0
                await db.execute(
                    """INSERT INTO strategy_performance (strategy_id, total_trades, win_trades, total_pnl, win_rate, peak_value, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
                       ON CONFLICT(strategy_id) DO UPDATE SET
                         total_trades=excluded.total_trades, win_trades=excluded.win_trades,
                         total_pnl=excluded.total_pnl, win_rate=excluded.win_rate, updated_at=datetime('now')""",
                    (strategy_id, total, wins, pnl, win_rate, abs(pnl) if pnl else 0)
                )
                await db.commit()
        except Exception as e:
            logger.error(f"[风控后检异常] {e}")
        finally:
            await db.close()

    async def _log_risk_event(self, event_type: str, strategy_id: int, message: str):
        db = await get_db()
        try:
            await db.execute(
                "INSERT INTO risk_events (event_type, strategy_id, message) VALUES (?, ?, ?)",
                (event_type, strategy_id, message)
            )
            await db.commit()
            logger.warning(f"[风控] {event_type}: {message}")
        finally:
            await db.close()

    async def check_market_circuit_breaker(self, market: str) -> bool:
        """市场级熔断检查，返回True表示可以交易"""
        if market == "A_SHARE":
            try:
                import akshare as ak
                df = ak.stock_zh_index_daily(symbol="sh000300")
                if not df.empty:
                    latest = df.iloc[-1]
                    change = (latest["close"] - latest["open"]) / latest["open"]
                    if change < -0.05:
                        return False
            except Exception:
                pass
        elif market == "US_STOCK":
            try:
                from data.us_stock_provider import get_current_price
                vix = get_current_price("^VIX")
                if vix and vix > 35:
                    return False
            except Exception:
                pass
        return True
