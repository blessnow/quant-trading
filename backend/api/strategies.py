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
