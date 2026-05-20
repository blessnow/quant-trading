"""双市场调度器 — APScheduler"""
import asyncio
import json
from datetime import datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from loguru import logger

import config
from data.market_status import CST, ET, is_trading_day, get_today_str
from database import get_db
from models import MarketContext, Signal, SignalType, Market
from strategies.registry import all_strategies, create_instance
from paper_broker import PaperBroker
from risk_manager import RiskManager

scheduler = AsyncIOScheduler(timezone="UTC")
broker = PaperBroker()
risk_mgr = RiskManager()

# 保存主事件循环引用，供线程池中的 job 提交协程
_main_loop: asyncio.AbstractEventLoop | None = None


def _run(coro):
    """从 APScheduler 线程池安全提交协程到主事件循环"""
    if _main_loop is None:
        logger.error("[调度器] 主事件循环未初始化")
        return
    asyncio.run_coroutine_threadsafe(coro, _main_loop)


async def run_strategy(strategy_name: str):
    """运行单个策略的完整流程"""
    db = await get_db()
    strategy_id = 0
    try:
        async with db.execute(
            "SELECT id, name, params_json, is_active, market FROM strategies WHERE name=?",
            (strategy_name,)
        ) as cur:
            row = await cur.fetchone()
        if not row or not row[3]:
            return

        strategy_id, name, params_json, _, market = row
        params = json.loads(params_json) if params_json else {}

        strategy_cls = all_strategies().get(strategy_name)
        if not strategy_cls:
            return

        strategy = strategy_cls(strategy_id, params)

        # 构建市场上下文 — 查询策略专属账户
        async with db.execute("SELECT cash FROM accounts WHERE strategy_id=? AND market=?", (strategy_id, market)) as cur:
            acct = await cur.fetchone()
        async with db.execute(
            "SELECT id, strategy_id, symbol, market, name, shares, avg_cost, buy_date, sellable_date, current_price "
            "FROM positions WHERE strategy_id=?", (strategy_id,)
        ) as cur:
            pos_rows = await cur.fetchall()

        from models import Position
        positions = []
        for p in pos_rows:
            positions.append(Position(
                id=p[0], strategy_id=p[1], symbol=p[2], market=Market(p[3]),
                name=p[4], shares=p[5], avg_cost=p[6], buy_date=p[7],
                sellable_date=p[8], current_price=p[9]
            ))

        context = MarketContext(
            account_cash=acct[0] if acct else 0,
            current_positions=positions,
            market=Market(market),
            trading_date=get_today_str(market),
            is_market_open=True,
        )

        # 风控预检
        decision = await risk_mgr.pre_check(strategy_id, context)
        if not decision:
            await _write_log(db, strategy_id, strategy_name, "warn", "风控拦截", decision.reason)
            return

        # 生成信号
        signals = strategy.generate_signals(context)

        # 提取信号中的 LLM 分析摘要
        analysis = ""
        for s in signals:
            if s.metadata and s.metadata.get("analysis"):
                analysis = s.metadata["analysis"]
                break
        if not analysis and hasattr(strategy, '_last_analysis') and strategy._last_analysis:
            analysis = strategy._last_analysis

        if not signals:
            await _write_log(db, strategy_id, strategy_name, "info", "无信号",
                             f"持仓{len(positions)}只, 现金{context.account_cash:.0f}" +
                             (f"\n分析: {analysis[:500]}" if analysis else ""))
            return

        # 执行信号
        executed = []
        rejected = []
        for signal in signals:
            signal.strategy_id = strategy_id
            validation = await risk_mgr.validate_signal(signal, context)
            if not validation:
                rejected.append(f"{signal.symbol} {validation.reason}")
                continue
            if validation.adjusted_shares > 0:
                signal.shares = validation.adjusted_shares

            trade = await broker.execute(signal)
            if trade:
                executed.append(trade)

        # 后检
        await risk_mgr.post_check(strategy_id, executed)
        strategy.on_execution_report(executed)

        # 写执行日志
        detail_parts = [f"信号{len(signals)}个, 成交{len(executed)}笔"]
        if rejected:
            detail_parts.append(f"拦截: {'; '.join(rejected[:3])}")
        for t in executed:
            detail_parts.append(f"{'买入' if t.side.value == 'BUY' else '卖出'} {t.symbol} {t.shares}股@{t.price}")
        level = "info" if executed else "warn"
        await _write_log(db, strategy_id, strategy_name, level, f"执行完成，成交{len(executed)}笔", "; ".join(detail_parts))

    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        logger.error(f"[调度异常] {strategy_name}: {e}\n{tb}")
        if strategy_id:
            await _write_log(db, strategy_id, strategy_name, "error", f"异常: {e}", tb[:500])
    finally:
        await db.close()


async def _write_log(db, strategy_id: int, strategy_name: str,
                     level: str, message: str, detail: str = ""):
    """写入策略执行日志并广播"""
    try:
        await db.execute(
            "INSERT INTO strategy_logs (strategy_id, strategy_name, level, message, detail) VALUES (?, ?, ?, ?, ?)",
            (strategy_id, strategy_name, level, message, detail),
        )
        await db.commit()
        
        # 广播日志到WebSocket
        from main import broadcast_log
        await broadcast_log({
            "strategy_id": strategy_id,
            "strategy_name": strategy_name,
            "level": level,
            "message": message,
            "detail": detail[:200] if detail else "",
            "time": datetime.now().strftime("%H:%M:%S"),
        })
    except Exception:
        pass


async def cleanup_old_logs():
    """清理7天前的策略日志"""
    db = await get_db()
    try:
        result = await db.execute(
            "DELETE FROM strategy_logs WHERE created_at < datetime('now', '-7 days')"
        )
        await db.commit()
        deleted = result.rowcount
        logger.info(f"[日志清理] 已清理 {deleted} 条7天前的策略日志")
    except Exception as e:
        logger.error(f"[日志清理] 失败: {e}")
    finally:
        await db.close()


async def snapshot_equity():
    """净值快照：市场级汇总 + 策略级 + 基准指数"""
    db = await get_db()
    try:
        for market in ["A_SHARE", "US_STOCK"]:
            # 汇总该市场所有策略账户的现金
            async with db.execute(
                "SELECT COALESCE(SUM(cash), 0), COALESCE(SUM(initial_capital), 0) FROM accounts WHERE strategy_id IS NOT NULL AND market=?",
                (market,)
            ) as cur:
                acct = await cur.fetchone()
            if not acct:
                continue

            cash = acct[0]
            initial = acct[1]

            # 计算持仓市值
            market_value = 0.0
            async with db.execute("SELECT shares, avg_cost, current_price, symbol FROM positions WHERE market=?", (market,)) as cur:
                positions = await cur.fetchall()
            for p in positions:
                shares, avg_cost, cur_price, symbol = p
                price = cur_price or avg_cost
                if market == "US_STOCK":
                    from data.us_stock_provider import get_usd_cny_rate
                    price = price * get_usd_cny_rate()
                market_value += shares * price

            total_value = cash + market_value
            unrealized_pnl = market_value - (initial - cash)
            daily_return = 0.0

            # 对比上一个快照
            async with db.execute(
                """SELECT total_value FROM equity_snapshots WHERE market=?
                   ORDER BY snapshot_date DESC, snapshot_time DESC LIMIT 1""",
                (market,)
            ) as cur:
                prev = await cur.fetchone()
            if prev and prev[0] > 0:
                daily_return = round((total_value - prev[0]) / prev[0] * 100, 4)

            today = get_today_str(market)
            now = datetime.now(CST if market == "A_SHARE" else ET)

            await db.execute(
                """INSERT OR REPLACE INTO equity_snapshots
                   (market, total_value, cash, unrealized_pnl, daily_return_pct, snapshot_date, snapshot_time)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (market, round(total_value, 2), round(cash, 2), round(unrealized_pnl, 2),
                 daily_return, today, now.strftime("%H:%M"))
            )
            logger.info(f"[净值快照] {market}: 总值={total_value:.0f} 现金={cash:.0f} 回报={daily_return:.2f}%")

        # === 策略级快照 ===
        async with db.execute("SELECT id, name, market FROM strategies WHERE is_active=1") as cur:
            strategy_rows = await cur.fetchall()
        for sid, sname, smarket in strategy_rows:
            # 策略专属账户现金
            async with db.execute(
                "SELECT cash FROM accounts WHERE strategy_id=? AND market=?", (sid, smarket)
            ) as cur:
                s_acct = await cur.fetchone()
            s_cash = s_acct[0] if s_acct else 0

            invested = 0.0
            market_value = 0.0
            async with db.execute(
                "SELECT shares, avg_cost, current_price FROM positions WHERE strategy_id=?", (sid,)
            ) as cur:
                pos_rows = await cur.fetchall()
            for p in pos_rows:
                shares, avg_cost, cur_price = p
                price = cur_price or avg_cost
                invested += shares * avg_cost
                if smarket == "US_STOCK":
                    from data.us_stock_provider import get_usd_cny_rate
                    price = price * get_usd_cny_rate()
                market_value += shares * price
            total_value = s_cash + market_value
            unrealized = market_value - invested
            s_daily_return = 0.0
            async with db.execute(
                """SELECT total_value FROM strategy_equity_snapshots WHERE strategy_id=?
                   ORDER BY snapshot_date DESC, snapshot_time DESC LIMIT 1""",
                (sid,)
            ) as cur:
                sprev = await cur.fetchone()
            if sprev and sprev[0] > 0:
                s_daily_return = round((total_value - sprev[0]) / sprev[0] * 100, 4)

            today = get_today_str(smarket)
            now = datetime.now(CST if smarket == "A_SHARE" else ET)
            await db.execute(
                """INSERT OR REPLACE INTO strategy_equity_snapshots
                   (strategy_id, total_value, invested, unrealized_pnl, daily_return_pct, snapshot_date, snapshot_time)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (sid, round(total_value, 2), round(invested, 2), round(unrealized, 2),
                 s_daily_return, today, now.strftime("%H:%M"))
            )

        # === 基准指数快照 ===
        await _snapshot_benchmarks(db)

        await db.commit()
        logger.info(f"[净值快照] 策略级快照完成 {len(strategy_rows)} 个策略")

    except Exception as e:
        logger.error(f"[净值快照异常] {e}")
    finally:
        await db.close()


async def _snapshot_benchmarks(db):
    """采集基准指数数据"""
    benchmarks = [
        ("sz399006", "创业板指", "A_SHARE"),
        ("sh000016", "上证50", "A_SHARE"),
        ("^NDX", "纳斯达克100", "US_STOCK"),
        ("^GSPC", "标普500", "US_STOCK"),
    ]
    for symbol, name, market in benchmarks:
        try:
            if market == "A_SHARE":
                from data.a_share_provider import get_index_history
            else:
                from data.us_stock_provider import get_index_history
            history = get_index_history(symbol, days=1)
            if not history:
                continue
            latest = history[-1]
            close_price = latest["close"]
            snapshot_date = latest["date"]

            # 计算累计收益率：对比最早的记录
            all_history = get_index_history(symbol, days=365)
            return_pct = 0.0
            if len(all_history) >= 2:
                first_close = all_history[0]["close"]
                if first_close > 0:
                    return_pct = round((close_price - first_close) / first_close * 100, 4)

            await db.execute(
                """INSERT OR REPLACE INTO benchmark_snapshots
                   (symbol, name, market, close_price, return_pct, snapshot_date)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (symbol, name, market, close_price, return_pct, snapshot_date)
            )
        except Exception as e:
            logger.debug(f"[基准快照] {symbol} 失败: {e}")


async def sell_a_share_pending():
    """A股T+1卖出：卖出可卖日期<=今天的持仓"""
    db = await get_db()
    try:
        today = get_today_str("A_SHARE")
        async with db.execute(
            "SELECT id, strategy_id, symbol, name, shares, avg_cost FROM positions "
            "WHERE market='A_SHARE' AND sellable_date <= ?",
            (today,)
        ) as cur:
            pending = await cur.fetchall()

        for p in pending:
            pos_id, strategy_id, symbol, name, shares, avg_cost = p
            from data.a_share_provider import get_current_price
            price = get_current_price(symbol)
            if not price:
                logger.warning(f"[A股卖出] 无法获取 {symbol} 价格，跳过")
                continue

            signal = Signal(
                signal_type=SignalType.SELL, symbol=symbol, market=Market.A_SHARE,
                name=name, price=price, shares=shares,
                metadata={"reason": "T+1到期自动卖出"}
            )
            signal.strategy_id = strategy_id
            trade = await broker.execute(signal)
            if trade:
                logger.info(f"[A股卖出] {symbol} 自动卖出完成")

    except Exception as e:
        logger.error(f"[A股卖出异常] {e}")
    finally:
        await db.close()


async def update_positions_realtime(market: str):
    """盘中实时更新所有持仓的当前价格"""
    db = await get_db()
    try:
        async with db.execute(
            "SELECT id, symbol, name, avg_cost FROM positions WHERE market=?", (market,)
        ) as cur:
            rows = await cur.fetchall()
        if not rows:
            return

        if market == "A_SHARE":
            from data.a_share_provider import get_batch_prices
            codes = [r[1] for r in rows]
            prices = get_batch_prices(codes)
        else:
            from data.us_stock_provider import get_current_price
            prices = {}
            for r in rows:
                symbol = r[1]
                price = get_current_price(symbol)
                if price:
                    prices[symbol] = price

        updated = 0
        for r in rows:
            pos_id, symbol, name, avg_cost = r
            price = prices.get(symbol)
            if price and price > 0:
                await db.execute(
                    "UPDATE positions SET current_price=?, updated_at=datetime('now') WHERE id=?",
                    (price, pos_id)
                )
                updated += 1

        # 更新账户现金不重复计算，只刷新市场价格
        await db.commit()
        if updated > 0:
            logger.debug(f"[实时行情] {market} 更新 {updated}/{len(rows)} 个持仓价格")
    except Exception as e:
        logger.error(f"[实时行情异常] {market}: {e}")
    finally:
        await db.close()


async def _check_position_for_sell(
    strategy_id: int,
    symbol: str,
    market: str,
    name: str,
    shares: float,
    avg_cost: float,
    cur_price: float,
    sellable: bool = True,
    stop_loss_pct: float = -8.0,
    take_profit_pct: float = 15.0,
):
    """检查单个持仓是否需要卖出"""
    if avg_cost <= 0 or cur_price <= 0:
        return None

    pnl_pct = (cur_price - avg_cost) / avg_cost * 100

    should_sell = False
    reason = ""

    if pnl_pct <= stop_loss_pct:
        should_sell = True
        reason = f"止损 {pnl_pct:.1f}% (阈值{stop_loss_pct:.1f}%)"
    elif pnl_pct >= take_profit_pct and sellable:
        should_sell = True
        reason = f"止盈 {pnl_pct:.1f}% (阈值{take_profit_pct:.1f}%)"

    if should_sell and sellable:
        logger.info(f"[持仓监控] {symbol} {reason}，触发卖出")
        signal = Signal(
            signal_type=SignalType.SELL,
            symbol=symbol,
            market=Market.A_SHARE if market == "A_SHARE" else Market.US_STOCK,
            name=name,
            price=cur_price,
            shares=shares,
            metadata={"reason": reason}
        )
        signal.strategy_id = strategy_id
        return await broker.execute(signal)
    return None


async def monitor_positions():
    """持仓监控：止损/止盈检查，盘中实时调仓"""
    db = await get_db()
    try:
        # A股：T+1当日不能卖，只卖 sellable_date <= today 的
        today_a = get_today_str("A_SHARE")
        async with db.execute(
            """SELECT p.id, p.strategy_id, p.symbol, p.market, p.name, p.shares,
                      p.avg_cost, p.current_price, p.sellable_date, p.stop_loss_pct, p.take_profit_pct
               FROM positions p WHERE p.market='A_SHARE' AND p.current_price IS NOT NULL"""
        ) as cur:
            a_rows = await cur.fetchall()

        for r in a_rows:
            pos_id, strategy_id, symbol, market, name, shares, avg_cost, cur_price, sellable_date, stop_loss_pct, take_profit_pct = r
            sellable = (sellable_date or "") <= today_a
            trade = await _check_position_for_sell(
                strategy_id, symbol, market, name, shares, avg_cost, cur_price,
                sellable=sellable,
                stop_loss_pct=stop_loss_pct if stop_loss_pct is not None else -8.0,
                take_profit_pct=take_profit_pct if take_profit_pct is not None else 15.0,
            )
            if trade:
                logger.info(f"[持仓监控] {symbol} 卖出成交")

        # 美股：T+0 随时可卖
        async with db.execute(
            """SELECT p.id, p.strategy_id, p.symbol, p.market, p.name, p.shares,
                      p.avg_cost, p.current_price, p.stop_loss_pct, p.take_profit_pct
               FROM positions p WHERE p.market='US_STOCK' AND p.current_price IS NOT NULL"""
        ) as cur:
            us_rows = await cur.fetchall()

        for r in us_rows:
            pos_id, strategy_id, symbol, market, name, shares, avg_cost, cur_price, stop_loss_pct, take_profit_pct = r
            trade = await _check_position_for_sell(
                strategy_id, symbol, market, name, shares, avg_cost, cur_price,
                sellable=True,
                stop_loss_pct=stop_loss_pct if stop_loss_pct is not None else -8.0,
                take_profit_pct=take_profit_pct if take_profit_pct is not None else 15.0,
            )
            if trade:
                logger.info(f"[持仓监控] {symbol} 卖出成交")

    except Exception as e:
        logger.error(f"[持仓监控异常] {e}")
    finally:
        await db.close()


async def check_alerts():
    """检查告警条件并发送通知"""
    db = await get_db()
    try:
        alerts = []
        
        # 1. 检查策略异常（最近1小时有错误日志）
        async with db.execute(
            """SELECT DISTINCT strategy_name, COUNT(*) as cnt 
               FROM strategy_logs 
               WHERE level='error' AND created_at > datetime('now', '-1 hour')
               GROUP BY strategy_id"""
        ) as cur:
            error_strategies = await cur.fetchall()
        
        for name, cnt in error_strategies:
            alerts.append(f"⚠️ 策略 {name} 最近1小时有 {cnt} 次错误")
        
        # 2. 检查持仓风险（单只股票亏损超过10%）
        async with db.execute(
            """SELECT symbol, name, avg_cost, current_price, 
                      (current_price - avg_cost) / avg_cost * 100 as pnl_pct
               FROM positions 
               WHERE current_price IS NOT NULL AND avg_cost > 0"""
        ) as cur:
            positions = await cur.fetchall()
        
        for symbol, name, avg_cost, cur_price, pnl_pct in positions:
            if pnl_pct <= -10:
                alerts.append(f"📉 {name}({symbol}) 亏损 {pnl_pct:.1f}%")
        
        # 3. 检查账户现金不足
        async with db.execute(
            "SELECT strategy_id, cash, initial_capital FROM accounts WHERE strategy_id IS NOT NULL"
        ) as cur:
            accounts = await cur.fetchall()
        
        for sid, cash, initial in accounts:
            if cash < initial * 0.1:
                alerts.append(f"💰 策略 {sid} 现金不足10%: {cash:.0f}")
        
        # 发送告警通知
        if alerts:
            from services.notifier import Notifier
            message = "📊 量化交易告警\n\n" + "\n".join(alerts)
            
            # 发送给所有配置了通知的用户
            async with db.execute(
                "SELECT DISTINCT user_id FROM notification_config WHERE is_enabled=1"
            ) as cur:
                users = await cur.fetchall()
            
            for user_id, in users:
                await Notifier.send_to_user(user_id, message)
            
            logger.warning(f"[告警] 发送 {len(alerts)} 条告警给 {len(users)} 个用户")
    
    except Exception as e:
        logger.error(f"[告警检查异常] {e}")
    finally:
        await db.close()


def setup_jobs():
    """注册所有调度任务"""

    # ========== A股 ==========
    # 盘前选股（9:00）— 多因子策略选股列表
    scheduler.add_job(
        run_strategy, "cron", hour=9, minute=0, timezone=CST, day_of_week="mon-fri",
        args=["MultiFactorDaily"],
        id="a_share_multi_factor", replace_existing=True, misfire_grace_time=300,
    )
    # 盘中扫描（每小时）— 涨停预判
    scheduler.add_job(
        run_strategy, "cron", minute="0", hour="9-14", timezone=CST, day_of_week="mon-fri",
        args=["LimitUpPredictor"],
        id="a_share_limit_up", replace_existing=True, misfire_grace_time=60,
    )
    # 盘中高频扫描（每30分钟）— 事件套利
    scheduler.add_job(
        run_strategy, "cron", minute="*/30", hour="9-14", timezone=CST, day_of_week="mon-fri",
        args=["EventArbitrage"],
        id="a_share_event", replace_existing=True, misfire_grace_time=120,
    )
    # 陈小群短线龙头 — 盘中扫描（每小时）
    scheduler.add_job(
        run_strategy, "cron", minute="30", hour="9-14", timezone=CST, day_of_week="mon-fri",
        args=["ChenXiaoqunShort"],
        id="chen_xiaoqun_intraday", replace_existing=True, misfire_grace_time=120,
    )
    # 鱼哥价值投资 — 每天早盘分析一次（9:35开盘后下单，用实时价格）
    scheduler.add_job(
        run_strategy, "cron", minute=35, hour=9, timezone=CST, day_of_week="mon-fri",
        args=["YuGeValue"],
        id="yu_ge_value", replace_existing=True, misfire_grace_time=600,
    )
    # T+1卖出
    scheduler.add_job(
        sell_a_share_pending, "cron", hour=9, minute=35, timezone=CST, day_of_week="mon-fri",
        id="a_share_sell", replace_existing=True, misfire_grace_time=300,
    )
    # 收盘快照
    scheduler.add_job(
        snapshot_equity, "cron", hour=15, minute=5, timezone=CST, day_of_week="mon-fri",
        id="a_share_snapshot", replace_existing=True, misfire_grace_time=300,
    )

    # ========== 美股 ==========
    # 开盘扫描（9:35 ET）— 跳空扫描
    scheduler.add_job(
        run_strategy, "cron", hour=9, minute=35, timezone=ET, day_of_week="mon-fri",
        args=["GapScanner"],
        id="us_gap", replace_existing=True, misfire_grace_time=300,
    )
    # 盘中高频扫描（每10分钟）— 动量突破
    scheduler.add_job(
        run_strategy, "cron", minute="*/10", hour="9-15", timezone=ET, day_of_week="mon-fri",
        args=["MomentumBreakout"],
        id="us_momentum", replace_existing=True, misfire_grace_time=60,
    )
    # 盘中高频扫描（每15分钟）— 均值回归
    scheduler.add_job(
        run_strategy, "cron", minute="*/15", hour="10-15", timezone=ET, day_of_week="mon-fri",
        args=["MeanReversion"],
        id="us_mean_reversion", replace_existing=True, misfire_grace_time=60,
    )
    # 收盘快照
    scheduler.add_job(
        snapshot_equity, "cron", hour=16, minute=5, timezone=ET, day_of_week="mon-fri",
        id="us_snapshot", replace_existing=True, misfire_grace_time=300,
    )

    # ========== 实时行情 + 盘中快照 + 持仓监控 ==========
    # A股盘中每2分钟更新持仓价格
    scheduler.add_job(
        update_positions_realtime, "cron", minute="*/2", hour="9-14", timezone=CST, day_of_week="mon-fri",
        args=["A_SHARE"],
        id="a_share_realtime", replace_existing=True, misfire_grace_time=60,
    )
    # 美股盘中每2分钟更新持仓价格
    scheduler.add_job(
        update_positions_realtime, "cron", minute="*/2", hour="9-15", timezone=ET, day_of_week="mon-fri",
        args=["US_STOCK"],
        id="us_stock_realtime", replace_existing=True, misfire_grace_time=60,
    )
    # A股盘中快照（每30分钟）
    scheduler.add_job(
        snapshot_equity, "cron", minute="0,30", hour="9-14", timezone=CST, day_of_week="mon-fri",
        id="a_share_intraday_snap", replace_existing=True, misfire_grace_time=120,
    )
    # 美股盘中快照（每30分钟）
    scheduler.add_job(
        snapshot_equity, "cron", minute="0,30", hour="9-15", timezone=ET, day_of_week="mon-fri",
        id="us_stock_intraday_snap", replace_existing=True, misfire_grace_time=120,
    )
    # A股持仓监控（每3分钟：止损/止盈）
    scheduler.add_job(
        monitor_positions, "cron", minute="*/3", hour="9-14", timezone=CST, day_of_week="mon-fri",
        id="a_share_monitor", replace_existing=True, misfire_grace_time=60,
    )
    # 美股持仓监控（每3分钟：止损/止盈）
    scheduler.add_job(
        monitor_positions, "cron", minute="*/3", hour="9-15", timezone=ET, day_of_week="mon-fri",
        id="us_stock_monitor", replace_existing=True, misfire_grace_time=60,
    )

    # 日志清理（每天凌晨2点，保留7天）
    scheduler.add_job(
        cleanup_old_logs, "cron", hour=2, minute=0, timezone=CST,
        id="cleanup_logs", replace_existing=True, misfire_grace_time=300,
    )

    # 告警检查（每30分钟）
    scheduler.add_job(
        check_alerts, "cron", minute="*/30", timezone=CST,
        id="check_alerts", replace_existing=True, misfire_grace_time=300,
    )

    logger.info(f"[调度器] 共注册 {len(scheduler.get_jobs())} 个任务")


def start_scheduler():
    global _main_loop
    try:
        _main_loop = asyncio.get_running_loop()
    except RuntimeError:
        _main_loop = asyncio.get_event_loop()
    setup_jobs()
    scheduler.start()
    logger.info("[调度器] 已启动")
