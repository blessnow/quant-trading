"""模拟交易执行引擎 — 支持A股和美股市场规则"""
import json
from datetime import datetime
from typing import Optional

from loguru import logger

import config
from data.market_status import get_next_trading_day, get_today_str, is_a_share_market_open, is_us_market_open, CST, ET
from database import get_db
from models import Signal, SignalType, Market, Trade, Side


class PaperBroker:
    """模拟券商，执行信号并记录交易"""

    async def execute(self, signal: Signal) -> Optional[Trade]:
        if signal.market == Market.A_SHARE:
            if not is_a_share_market_open():
                logger.warning(f"[A股] 非交易时段，拒绝执行 {signal.symbol}")
                return None
            return await self._execute_a_share(signal)
        elif signal.market == Market.US_STOCK:
            if not is_us_market_open():
                logger.warning(f"[美股] 非交易时段，拒绝执行 {signal.symbol}")
                return None
            return await self._execute_us(signal)
        logger.error(f"未知市场: {signal.market}")
        return None

    async def _execute_a_share(self, signal: Signal) -> Optional[Trade]:
        db = await get_db()
        try:
            today = get_today_str("A_SHARE")
            now_cst = datetime.now(CST).strftime("%Y-%m-%d %H:%M:%S")

            if signal.signal_type == SignalType.BUY:
                # 100股整手
                lots = int(signal.shares // 100)
                if lots < 1:
                    logger.warning(f"[A股] 不足1手，拒绝: {signal.symbol} {signal.shares}股")
                    return None
                shares = lots * 100

                # 滑点（买入价上浮0.1%）
                price = round(signal.price * 1.001, 2)
                notional = price * shares

                # 手续费
                commission = max(notional * config.A_SHARE_COMMISSION_RATE, config.A_SHARE_COMMISSION_MIN)
                total_cost = notional + commission

                # 检查资金
                async with db.execute("SELECT cash FROM accounts WHERE strategy_id=? AND market='A_SHARE'", (signal.strategy_id,)) as cur:
                    row = await cur.fetchone()
                if not row or row[0] < total_cost:
                    logger.warning(f"[A股] 资金不足: 需要{total_cost:.0f}, 可用{row[0] if row else 0:.0f}")
                    return None

                # 检查是否已持有
                async with db.execute(
                    "SELECT id, shares FROM positions WHERE symbol=? AND market='A_SHARE'",
                    (signal.symbol,)
                ) as cur:
                    existing = await cur.fetchone()

                if existing:
                    logger.warning(f"[A股] 已持有 {signal.symbol}，跳过")
                    return None

                # T+1: 次一交易日才可卖
                sellable_date = get_next_trading_day("A_SHARE", today) or today

                # 扣资金
                await db.execute(
                    "UPDATE accounts SET cash=cash-?, updated_at=? WHERE strategy_id=? AND market='A_SHARE'",
                    (total_cost, now_cst, signal.strategy_id)
                )

                # 记录持仓
                await db.execute(
                    """INSERT INTO positions (strategy_id, symbol, market, name, shares, avg_cost, buy_date, sellable_date, current_price)
                       VALUES (?, ?, 'A_SHARE', ?, ?, ?, ?, ?, ?)""",
                    (signal.strategy_id, signal.symbol, signal.name, shares, price, today, sellable_date, price)
                )

                # 记录交易
                await db.execute(
                    """INSERT INTO trades (strategy_id, symbol, market, name, side, price, shares, notional, commission, slippage, signal_data, executed_at)
                       VALUES (?, ?, 'A_SHARE', ?, 'BUY', ?, ?, ?, ?, ?, ?, ?)""",
                    (signal.strategy_id, signal.symbol, signal.name, price, shares, notional, commission,
                     round(price - signal.price, 2), json.dumps(signal.metadata, ensure_ascii=False), now_cst)
                )
                await db.commit()

                trade = Trade(0, signal.strategy_id, signal.symbol, Market.A_SHARE, signal.name,
                              Side.BUY, price, shares, notional, commission, round(price - signal.price, 2),
                              executed_at=now_cst)
                logger.info(f"[A股买入] {signal.symbol} {signal.name} {shares}股 @ {price} 总额{notional:.0f}")
                return trade

            elif signal.signal_type == SignalType.SELL:
                async with db.execute(
                    "SELECT id, shares, avg_cost, buy_date, sellable_date FROM positions WHERE symbol=? AND market='A_SHARE'",
                    (signal.symbol,)
                ) as cur:
                    pos = await cur.fetchone()

                if not pos:
                    logger.warning(f"[A股] 未持有 {signal.symbol}，无法卖出")
                    return None

                pos_id, held_shares, avg_cost, buy_date, sellable_date = pos

                # T+1检查
                if sellable_date and today < sellable_date:
                    logger.warning(f"[A股] T+1限制: {signal.symbol} 今日不可卖 (可卖日={sellable_date})")
                    return None

                sell_shares = min(int(signal.shares), int(held_shares))
                if sell_shares < 1:
                    return None

                # 滑点（卖出价下浮0.1%）
                price = round(signal.price * 0.999, 2)
                notional = price * sell_shares

                # 手续费 + 印花税
                commission = max(notional * config.A_SHARE_COMMISSION_RATE, config.A_SHARE_COMMISSION_MIN)
                stamp_tax = notional * config.A_SHARE_STAMP_TAX_RATE

                # 盈亏
                pnl = (price - avg_cost) * sell_shares - commission - stamp_tax

                # 加资金
                net_proceeds = notional - commission - stamp_tax
                await db.execute(
                    "UPDATE accounts SET cash=cash+?, updated_at=? WHERE strategy_id=? AND market='A_SHARE'",
                    (net_proceeds, now_cst, signal.strategy_id)
                )

                # 删持仓
                await db.execute("DELETE FROM positions WHERE id=?", (pos_id,))

                # 记录交易
                await db.execute(
                    """INSERT INTO trades (strategy_id, symbol, market, name, side, price, shares, notional, commission, slippage, pnl, signal_data, executed_at)
                       VALUES (?, ?, 'A_SHARE', ?, 'SELL', ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (signal.strategy_id, signal.symbol, signal.name, price, sell_shares, notional,
                     commission + stamp_tax, round(signal.price - price, 2), round(pnl, 2),
                     json.dumps(signal.metadata, ensure_ascii=False), now_cst)
                )
                await db.commit()

                trade = Trade(0, signal.strategy_id, signal.symbol, Market.A_SHARE, signal.name,
                              Side.SELL, price, sell_shares, notional, commission + stamp_tax,
                              round(signal.price - price, 2), round(pnl, 2), executed_at=now_cst)
                logger.info(f"[A股卖出] {signal.symbol} {signal.name} {sell_shares}股 @ {price} 盈亏={pnl:.0f}")
                return trade

        except Exception as e:
            logger.error(f"[A股执行异常] {e}")
            await db.rollback()
            return None
        finally:
            await db.close()

    async def _execute_us(self, signal: Signal) -> Optional[Trade]:
        db = await get_db()
        try:
            today = get_today_str("US_STOCK")
            now_et = datetime.now(ET).strftime("%Y-%m-%d %H:%M:%S")

            if signal.signal_type == SignalType.BUY:
                shares = signal.shares
                price = round(signal.price * 1.001, 2)  # 滑点
                notional = price * shares
                commission = max(shares * config.US_STOCK_COMMISSION_PER_SHARE, config.US_STOCK_MIN_COMMISION)
                total_cost = notional + commission

                # 汇率转换（美股账户用RMB记账）
                from data.us_stock_provider import get_usd_cny_rate
                rate = get_usd_cny_rate()
                total_cost_rmb = total_cost * rate

                async with db.execute("SELECT cash FROM accounts WHERE strategy_id=? AND market='US_STOCK'", (signal.strategy_id,)) as cur:
                    row = await cur.fetchone()
                if not row or row[0] < total_cost_rmb:
                    logger.warning(f"[美股] 资金不足: 需要${total_cost:.0f}(¥{total_cost_rmb:.0f}), 可用¥{row[0] if row else 0:.0f}")
                    return None

                await db.execute(
                    "UPDATE accounts SET cash=cash-?, updated_at=? WHERE strategy_id=? AND market='US_STOCK'",
                    (total_cost_rmb, now_et, signal.strategy_id)
                )

                await db.execute(
                    """INSERT INTO positions (strategy_id, symbol, market, name, shares, avg_cost, buy_date, sellable_date, current_price)
                       VALUES (?, ?, 'US_STOCK', ?, ?, ?, ?, ?, ?)""",
                    (signal.strategy_id, signal.symbol, signal.name, shares, price, today, today, price)
                )

                await db.execute(
                    """INSERT INTO trades (strategy_id, symbol, market, name, side, price, shares, notional, commission, slippage, signal_data, executed_at)
                       VALUES (?, ?, 'US_STOCK', ?, 'BUY', ?, ?, ?, ?, ?, ?, ?)""",
                    (signal.strategy_id, signal.symbol, signal.name, price, shares, notional, commission,
                     round(price - signal.price, 2), json.dumps(signal.metadata, ensure_ascii=False), now_et)
                )
                await db.commit()

                trade = Trade(0, signal.strategy_id, signal.symbol, Market.US_STOCK, signal.name,
                              Side.BUY, price, shares, notional, commission, round(price - signal.price, 2),
                              executed_at=now_et)
                logger.info(f"[美股买入] {signal.symbol} {shares}股 @ ${price}")
                return trade

            elif signal.signal_type == SignalType.SELL:
                async with db.execute(
                    "SELECT id, shares, avg_cost FROM positions WHERE symbol=? AND market='US_STOCK'",
                    (signal.symbol,)
                ) as cur:
                    pos = await cur.fetchone()

                if not pos:
                    logger.warning(f"[美股] 未持有 {signal.symbol}")
                    return None

                pos_id, held_shares, avg_cost = pos
                sell_shares = min(signal.shares, held_shares)
                price = round(signal.price * 0.999, 2)
                notional = price * sell_shares
                commission = max(sell_shares * config.US_STOCK_COMMISSION_PER_SHARE, config.US_STOCK_MIN_COMMISION)

                from data.us_stock_provider import get_usd_cny_rate
                rate = get_usd_cny_rate()

                pnl_usd = (price - avg_cost) * sell_shares - commission
                net_proceeds_rmb = (notional - commission) * rate

                await db.execute(
                    "UPDATE accounts SET cash=cash+?, updated_at=? WHERE strategy_id=? AND market='US_STOCK'",
                    (net_proceeds_rmb, now_et, signal.strategy_id)
                )
                await db.execute("DELETE FROM positions WHERE id=?", (pos_id,))

                await db.execute(
                    """INSERT INTO trades (strategy_id, symbol, market, name, side, price, shares, notional, commission, slippage, pnl, signal_data, executed_at)
                       VALUES (?, ?, 'US_STOCK', ?, 'SELL', ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (signal.strategy_id, signal.symbol, signal.name, price, sell_shares, notional, commission,
                     round(signal.price - price, 2), round(pnl_usd, 2),
                     json.dumps(signal.metadata, ensure_ascii=False), now_et)
                )
                await db.commit()

                trade = Trade(0, signal.strategy_id, signal.symbol, Market.US_STOCK, signal.name,
                              Side.SELL, price, sell_shares, notional, commission,
                              round(signal.price - price, 2), round(pnl_usd, 2), executed_at=now_et)
                logger.info(f"[美股卖出] {signal.symbol} {sell_shares}股 @ ${price} PnL=${pnl_usd:.2f}")
                return trade

        except Exception as e:
            logger.error(f"[美股执行异常] {e}")
            await db.rollback()
            return None
        finally:
            await db.close()
