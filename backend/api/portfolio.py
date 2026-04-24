"""组合/持仓/净值 API"""
from fastapi import APIRouter

from database import get_db

router = APIRouter(prefix="/api/portfolio", tags=["portfolio"])


@router.get("/best-strategy")
async def get_best_strategy(days: int = 90):
    """获取当天收益最高的策略 + 其曲线 + 基准"""
    db = await get_db()
    try:
        # 找今天收益最高的策略
        async with db.execute("""
            SELECT strategy_id, total_value, invested, unrealized_pnl, daily_return_pct
            FROM strategy_equity_snapshots
            WHERE snapshot_date = (SELECT MAX(snapshot_date) FROM strategy_equity_snapshots)
            ORDER BY daily_return_pct DESC
            LIMIT 1
        """) as cur:
            best = await cur.fetchone()

        if not best:
            # 无快照数据时取策略绩效最高的
            async with db.execute("""
                SELECT s.id, s.name, s.display_name, s.market,
                       sp.total_pnl, sp.total_trades
                FROM strategies s LEFT JOIN strategy_performance sp ON s.id = sp.strategy_id
                WHERE s.is_active=1
                ORDER BY sp.total_pnl DESC LIMIT 1
            """) as cur:
                fallback = await cur.fetchone()
            if not fallback:
                return {"strategy": None, "curve": [], "benchmarks": []}
            sid = fallback[0]
            strategy_info = {
                "id": sid, "name": fallback[1], "display_name": fallback[2],
                "market": fallback[3], "daily_pnl": fallback[4] or 0,
                "daily_return_pct": 0, "total_trades": fallback[5] or 0,
            }
        else:
            sid = best[0]
            async with db.execute(
                "SELECT name, display_name, market FROM strategies WHERE id=?", (sid,)
            ) as cur:
                srow = await cur.fetchone()
            strategy_info = {
                "id": sid, "name": srow[0], "display_name": srow[1],
                "market": srow[2], "daily_pnl": round(best[3], 2),
                "daily_return_pct": best[4], "total_value": round(best[1], 2),
            }

        # 策略曲线
        curve = []
        async with db.execute(
            """SELECT snapshot_date, total_value, invested, unrealized_pnl, daily_return_pct
               FROM strategy_equity_snapshots WHERE strategy_id=?
               AND snapshot_date >= date('now', ?||' days')
               ORDER BY snapshot_date, snapshot_time""",
            (sid, str(-days))
        ) as cur:
            rows = await cur.fetchall()
        for r in rows:
            curve.append({
                "date": r[0], "total_value": r[1], "invested": r[2],
                "unrealized_pnl": r[3], "daily_return_pct": r[4],
            })

        # 如果没有策略快照，用市场级快照替代
        if not curve:
            market = strategy_info.get("market", "A_SHARE")
            async with db.execute(
                """SELECT snapshot_date, total_value, cash, unrealized_pnl, daily_return_pct
                   FROM equity_snapshots WHERE market=?
                   AND snapshot_date >= date('now', ?||' days')
                   ORDER BY snapshot_date, snapshot_time""",
                (market, str(-days))
            ) as cur:
                rows = await cur.fetchall()
            for r in rows:
                curve.append({
                    "date": r[0], "total_value": r[1], "invested": r[2],
                    "unrealized_pnl": r[3], "daily_return_pct": r[4],
                })

        # 基准曲线
        market = strategy_info.get("market", "A_SHARE")
        benchmarks = []
        async with db.execute(
            """SELECT DISTINCT symbol, name FROM benchmark_snapshots WHERE market=?""",
            (market,)
        ) as cur:
            bm_rows = await cur.fetchall()
        for bm in bm_rows:
            bm_curve = []
            async with db.execute(
                """SELECT snapshot_date, return_pct, close_price
                   FROM benchmark_snapshots WHERE symbol=?
                   AND snapshot_date >= date('now', ?||' days')
                   ORDER BY snapshot_date""",
                (bm[0], str(-days))
            ) as cur:
                bm_data = await cur.fetchall()
            for b in bm_data:
                bm_curve.append({"date": b[0], "return_pct": b[1], "close": b[2]})
            benchmarks.append({"name": bm[1], "symbol": bm[0], "curve": bm_curve})

        return {"strategy": strategy_info, "curve": curve, "benchmarks": benchmarks}
    finally:
        await db.close()


@router.get("/benchmarks")
async def get_benchmarks(market: str = None, days: int = 90):
    """获取基准指数收益率曲线"""
    db = await get_db()
    try:
        conditions = ["snapshot_date >= date('now', ?||' days')"]
        params = [str(-days)]
        if market:
            conditions.append("market=?")
            params.append(market)

        # 获取所有基准symbol
        async with db.execute(
            "SELECT DISTINCT symbol, name, market FROM benchmark_snapshots"
            + (" WHERE market=?" if market else ""),
            [market] if market else []
        ) as cur:
            bm_list = await cur.fetchall()

        benchmarks = []
        for bm in bm_list:
            bm_curve = []
            async with db.execute(
                """SELECT snapshot_date, return_pct, close_price
                   FROM benchmark_snapshots WHERE symbol=? AND snapshot_date >= date('now', ?||' days')
                   ORDER BY snapshot_date""",
                (bm[0], str(-days))
            ) as cur:
                rows = await cur.fetchall()
            for r in rows:
                bm_curve.append({"date": r[0], "return_pct": r[1], "close": r[2]})
            benchmarks.append({"name": bm[1], "symbol": bm[0], "market": bm[2], "curve": bm_curve})

        return {"benchmarks": benchmarks}
    finally:
        await db.close()


@router.get("/summary")
async def get_summary():
    db = await get_db()
    try:
        result = {"total_value": 0, "daily_pnl": 0, "daily_return_pct": 0, "markets": {}}
        total_value = 0
        total_initial = 0

        for market in ["A_SHARE", "US_STOCK"]:
            # 汇总该市场所有策略账户
            async with db.execute(
                "SELECT COALESCE(SUM(cash), 0), COALESCE(SUM(initial_capital), 0) FROM accounts WHERE strategy_id IS NOT NULL AND market=?",
                (market,)
            ) as cur:
                acct = await cur.fetchone()
            if not acct:
                continue
            cash, initial = acct

            market_value = 0
            async with db.execute("SELECT shares, avg_cost, current_price FROM positions WHERE market=?", (market,)) as cur:
                positions = await cur.fetchall()
            for p in positions:
                shares, avg_cost, cur_price = p
                price = cur_price or avg_cost
                if market == "US_STOCK":
                    from data.us_stock_provider import get_usd_cny_rate
                    price = price * get_usd_cny_rate()
                market_value += shares * price

            mv = cash + market_value
            total_value += mv
            total_initial += initial
            pnl = mv - initial

            # 最新快照
            async with db.execute(
                """SELECT daily_return_pct FROM equity_snapshots WHERE market=?
                   ORDER BY snapshot_date DESC, snapshot_time DESC LIMIT 1""",
                (market,)
            ) as cur:
                snap = await cur.fetchone()
            daily_ret = snap[0] if snap else 0

            result["markets"][market] = {
                "cash": round(cash, 2),
                "market_value": round(market_value, 2),
                "total": round(mv, 2),
                "initial_capital": initial,
                "total_pnl": round(pnl, 2),
                "daily_return_pct": daily_ret,
            }

        result["total_value"] = round(total_value, 2)
        result["initial_capital"] = total_initial
        result["total_pnl"] = round(total_value - total_initial, 2)

        return result
    finally:
        await db.close()


@router.get("/positions")
async def get_positions(market: str = None):
    db = await get_db()
    try:
        query = """
            SELECT p.id, p.strategy_id, s.display_name, p.symbol, p.market, p.name,
                   p.shares, p.avg_cost, p.current_price, p.buy_date, p.sellable_date
            FROM positions p LEFT JOIN strategies s ON p.strategy_id = s.id
        """
        params = []
        if market:
            query += " WHERE p.market=?"
            params.append(market)

        async with db.execute(query, params) as cur:
            rows = await cur.fetchall()

        positions = []
        for r in rows:
            cur_price = r[8] or r[7]
            unrealized = (cur_price - r[7]) * r[6] if r[7] > 0 else 0
            pct = (cur_price - r[7]) / r[7] * 100 if r[7] > 0 else 0
            positions.append({
                "id": r[0], "strategy_id": r[1], "strategy_name": r[2],
                "symbol": r[3], "market": r[4], "name": r[5],
                "shares": r[6], "avg_cost": r[7], "current_price": r[8],
                "buy_date": r[9], "sellable_date": r[10],
                "unrealized_pnl": round(unrealized, 2),
                "unrealized_pnl_pct": round(pct, 2),
                "market_value": round(cur_price * r[6], 2),
            })
        return {"positions": positions, "total": len(positions)}
    finally:
        await db.close()


@router.get("/equity-curve")
async def get_equity_curve(days: int = 90, market: str = None, strategy_id: int = None):
    db = await get_db()
    try:
        # 策略级曲线
        if strategy_id:
            query = """
                SELECT strategy_id, total_value, invested, unrealized_pnl,
                       daily_return_pct, snapshot_date, snapshot_time
                FROM strategy_equity_snapshots
            """
            params = []
            conditions = ["strategy_id=?"]
            params.append(strategy_id)
            conditions.append(f"snapshot_date >= date('now', '-{days} days')")
            query += " WHERE " + " AND ".join(conditions)
            query += " ORDER BY snapshot_date, snapshot_time"

            async with db.execute(query, params) as cur:
                rows = await cur.fetchall()

            curve = []
            for r in rows:
                curve.append({
                    "strategy_id": r[0], "total_value": r[1], "invested": r[2],
                    "unrealized_pnl": r[3], "daily_return_pct": r[4],
                    "date": r[5], "time": r[6],
                })
            return {"curve": curve, "count": len(curve), "level": "strategy"}

        # 市场级曲线（原有逻辑）
        query = """
            SELECT market, total_value, cash, unrealized_pnl, daily_return_pct,
                   snapshot_date, snapshot_time
            FROM equity_snapshots
        """
        params = []
        conditions = []
        if market:
            conditions.append("market=?")
            params.append(market)
        conditions.append(f"snapshot_date >= date('now', '-{days} days')")
        query += " WHERE " + " AND ".join(conditions) if conditions else ""
        query += " ORDER BY snapshot_date, snapshot_time"

        async with db.execute(query, params) as cur:
            rows = await cur.fetchall()

        curve = []
        for r in rows:
            curve.append({
                "market": r[0], "total_value": r[1], "cash": r[2],
                "unrealized_pnl": r[3], "daily_return_pct": r[4],
                "date": r[5], "time": r[6],
            })
        return {"curve": curve, "count": len(curve), "level": "market"}
    finally:
        await db.close()
