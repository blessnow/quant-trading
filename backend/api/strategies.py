"""策略管理 API"""
import json

from fastapi import APIRouter
from pydantic import BaseModel

from database import get_db

router = APIRouter(prefix="/api/strategies", tags=["strategies"])


@router.get("")
async def list_strategies():
    db = await get_db()
    try:
        async with db.execute("""
            SELECT s.id, s.name, s.display_name, s.market, s.description,
                   s.params_json, s.is_active, s.max_position_pct,
                   sp.total_trades, sp.win_trades, sp.total_pnl, sp.win_rate, sp.sharpe_ratio
            FROM strategies s LEFT JOIN strategy_performance sp ON s.id = sp.strategy_id
        """) as cur:
            rows = await cur.fetchall()

        strategies = []
        for r in rows:
            strategies.append({
                "id": r[0], "name": r[1], "display_name": r[2], "market": r[3],
                "description": r[4], "params": json.loads(r[5]) if r[5] else {},
                "is_active": bool(r[6]), "max_position_pct": r[7],
                "performance": {
                    "total_trades": r[8] or 0, "win_trades": r[9] or 0,
                    "total_pnl": r[10] or 0, "win_rate": r[11] or 0,
                    "sharpe_ratio": r[12],
                } if r[8] else None,
            })
        return {"strategies": strategies}
    finally:
        await db.close()


class ToggleRequest(BaseModel):
    is_active: bool


@router.put("/{strategy_id}/toggle")
async def toggle_strategy(strategy_id: int, req: ToggleRequest):
    db = await get_db()
    try:
        await db.execute(
            "UPDATE strategies SET is_active=? WHERE id=?",
            (1 if req.is_active else 0, strategy_id)
        )
        await db.commit()
        return {"success": True, "strategy_id": strategy_id, "is_active": req.is_active}
    finally:
        await db.close()


class ParamsRequest(BaseModel):
    params: dict


@router.put("/{strategy_id}/params")
async def update_params(strategy_id: int, req: ParamsRequest):
    db = await get_db()
    try:
        # 保存历史
        async with db.execute("SELECT params_json FROM strategies WHERE id=?", (strategy_id,)) as cur:
            row = await cur.fetchone()
        old_params = row[0] if row else "{}"

        await db.execute(
            "UPDATE strategies SET params_json=? WHERE id=?",
            (json.dumps(req.params, ensure_ascii=False), strategy_id)
        )
        await db.execute(
            "INSERT INTO strategy_param_history (strategy_id, old_params, new_params, reason) VALUES (?, ?, ?, ?)",
            (strategy_id, old_params, json.dumps(req.params, ensure_ascii=False), "手动修改")
        )
        await db.commit()
        return {"success": True}
    finally:
        await db.close()


@router.get("/ranking")
async def strategy_ranking(period: str = "month"):
    """策略排行榜"""
    db = await get_db()
    try:
        async with db.execute("""
            SELECT s.id, s.display_name, s.market,
                   sp.total_trades, sp.total_pnl, sp.win_rate, sp.sharpe_ratio, sp.max_drawdown_pct
            FROM strategies s LEFT JOIN strategy_performance sp ON s.id = sp.strategy_id
            WHERE s.is_active=1
        """) as cur:
            rows = await cur.fetchall()

        rankings = []
        for r in rows:
            sid, name, market, trades, pnl, win_rate, sharpe, dd = r
            trades = trades or 0
            pnl = pnl or 0
            win_rate = win_rate or 0
            sharpe = sharpe or 0
            dd = dd or 0

            # 综合评分
            score = (
                0.30 * min(sharpe / 2, 1) * 100 +
                0.25 * min(max(pnl, 0) / 10000, 1) * 100 +
                0.20 * win_rate * 100 +
                0.15 * (1 - min(dd / 0.2, 1)) * 100 +
                0.10 * min(trades / 50, 1) * 100
            )

            rankings.append({
                "strategy_id": sid, "display_name": name, "market": market,
                "total_trades": trades, "total_pnl": round(pnl, 2),
                "win_rate": round(win_rate, 4), "sharpe_ratio": round(sharpe, 2),
                "max_drawdown": round(dd, 4), "score": round(score, 1),
            })

        rankings.sort(key=lambda x: x["score"], reverse=True)
        return {"rankings": rankings, "period": period}
    finally:
        await db.close()


@router.get("/logs")
async def strategy_logs(strategy_id: int = None, limit: int = 100):
    """策略执行日志"""
    db = await get_db()
    try:
        if strategy_id:
            async with db.execute(
                "SELECT id, strategy_id, strategy_name, level, message, detail, created_at "
                "FROM strategy_logs WHERE strategy_id=? ORDER BY id DESC LIMIT ?",
                (strategy_id, limit)
            ) as cur:
                rows = await cur.fetchall()
        else:
            async with db.execute(
                "SELECT id, strategy_id, strategy_name, level, message, detail, created_at "
                "FROM strategy_logs ORDER BY id DESC LIMIT ?",
                (limit,)
            ) as cur:
                rows = await cur.fetchall()

        logs = []
        for r in rows:
            logs.append({
                "id": r[0], "strategy_id": r[1], "strategy_name": r[2],
                "level": r[3], "message": r[4], "detail": r[5], "created_at": r[6],
            })
        return {"logs": logs, "count": len(logs)}
    finally:
        await db.close()


@router.get("/{strategy_id}")
async def get_strategy(strategy_id: int):
    """获取单个策略详情"""
    db = await get_db()
    try:
        async with db.execute("""
            SELECT s.id, s.name, s.display_name, s.market, s.description,
                   s.params_json, s.is_active, s.max_position_pct,
                   sp.total_trades, sp.win_trades, sp.total_pnl, sp.win_rate, 
                   sp.sharpe_ratio, sp.max_drawdown_pct
            FROM strategies s LEFT JOIN strategy_performance sp ON s.id = sp.strategy_id
            WHERE s.id=?
        """, (strategy_id,)) as cur:
            row = await cur.fetchone()

        if not row:
            return {"error": "策略不存在"}

        return {
            "id": row[0], "name": row[1], "display_name": row[2], "market": row[3],
            "description": row[4], "params": json.loads(row[5]) if row[5] else {},
            "is_active": bool(row[6]), "max_position_pct": row[7],
            "performance": {
                "total_trades": row[8] or 0, "win_trades": row[9] or 0,
                "total_pnl": row[10] or 0, "win_rate": row[11] or 0,
                "sharpe_ratio": row[12], "max_drawdown_pct": row[13] or 0,
            } if row[8] else None,
        }
    finally:
        await db.close()


@router.get("/{strategy_id}/equity-curve")
async def strategy_equity_curve(strategy_id: int, days: int = 90):
    """策略收益曲线（每天只返回最新一条）"""
    db = await get_db()
    try:
        async with db.execute("""
            SELECT snapshot_date, total_value, invested, unrealized_pnl, daily_return_pct, MAX(snapshot_time)
            FROM strategy_equity_snapshots
            WHERE strategy_id=?
            GROUP BY snapshot_date
            ORDER BY snapshot_date DESC
            LIMIT ?
        """, (strategy_id, days)) as cur:
            rows = await cur.fetchall()

        curve = []
        for r in reversed(rows):
            curve.append({
                "date": r[0], "total_value": r[1], "invested": r[2],
                "unrealized_pnl": r[3], "daily_return_pct": r[4],
            })
        return {"curve": curve, "count": len(curve)}
    finally:
        await db.close()


@router.get("/{strategy_id}/positions")
async def strategy_positions(strategy_id: int):
    """策略当前持仓"""
    db = await get_db()
    try:
        async with db.execute("""
            SELECT id, symbol, market, name, shares, avg_cost, current_price, buy_date, sellable_date
            FROM positions WHERE strategy_id=?
        """, (strategy_id,)) as cur:
            rows = await cur.fetchall()

        positions = []
        for r in rows:
            shares, avg_cost, current_price = r[4], r[5], r[6] or r[5]
            unrealized_pnl = (current_price - avg_cost) * shares
            unrealized_pnl_pct = (current_price - avg_cost) / avg_cost if avg_cost else 0
            market_value = shares * current_price
            positions.append({
                "id": r[0], "symbol": r[1], "market": r[2], "name": r[3],
                "shares": shares, "avg_cost": avg_cost, "current_price": current_price,
                "unrealized_pnl": round(unrealized_pnl, 2), "unrealized_pnl_pct": round(unrealized_pnl_pct, 4),
                "market_value": round(market_value, 2), "buy_date": r[7], "sellable_date": r[8],
            })
        return {"positions": positions, "count": len(positions)}
    finally:
        await db.close()


@router.get("/{strategy_id}/trades")
async def strategy_trades(strategy_id: int, limit: int = 20, offset: int = 0):
    """策略历史交易（支持分页）"""
    db = await get_db()
    try:
        # 获取总数
        async with db.execute("SELECT COUNT(*) FROM trades WHERE strategy_id=?", (strategy_id,)) as cur:
            total = await cur.fetchone()
            total = total[0] if total else 0

        # 获取分页数据
        async with db.execute("""
            SELECT id, symbol, market, name, side, price, shares, notional,
                   commission, pnl, executed_at
            FROM trades WHERE strategy_id=?
            ORDER BY id DESC LIMIT ? OFFSET ?
        """, (strategy_id, limit, offset)) as cur:
            rows = await cur.fetchall()

        trades = []
        for r in rows:
            trades.append({
                "id": r[0], "symbol": r[1], "market": r[2], "name": r[3],
                "side": r[4], "price": r[5], "shares": r[6], "notional": r[7],
                "commission": r[8], "pnl": r[9], "executed_at": r[10],
            })
        return {"trades": trades, "total": total, "has_more": offset + len(trades) < total}
    finally:
        await db.close()
