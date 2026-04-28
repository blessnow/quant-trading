"""交易记录 API"""
from fastapi import APIRouter, Header, HTTPException
from typing import Optional

from database import get_db
from api.wechat_auth import verify_token

router = APIRouter(prefix="/api/trades", tags=["trades"])


async def require_member(authorization: Optional[str] = None):
    payload = verify_token(authorization)
    if not payload:
        raise HTTPException(status_code=401, detail="未登录")
    db = await get_db()
    try:
        async with db.execute(
            "SELECT is_member, is_admin FROM users WHERE id=?", (payload["user_id"],)
        ) as cur:
            row = await cur.fetchone()
        if not row:
            raise HTTPException(status_code=401, detail="用户不存在")
        if not row[0] and not row[1]:
            raise HTTPException(status_code=403, detail="需要会员权限")
        return payload
    finally:
        await db.close()


@router.get("")
async def list_trades(
    strategy_id: int = None,
    market: str = None,
    side: str = None,
    limit: int = 100,
    offset: int = 0,
    authorization: Optional[str] = Header(None),
):
    await require_member(authorization)
    db = await get_db()
    try:
        query = """
            SELECT t.id, t.strategy_id, s.display_name, t.symbol, t.market, t.name,
                   t.side, t.price, t.shares, t.notional, t.commission, t.slippage,
                   t.pnl, t.signal_data, t.executed_at
            FROM trades t LEFT JOIN strategies s ON t.strategy_id = s.id
        """
        conditions = []
        params = []
        if strategy_id:
            conditions.append("t.strategy_id=?")
            params.append(strategy_id)
        if market:
            conditions.append("t.market=?")
            params.append(market)
        if side:
            conditions.append("t.side=?")
            params.append(side)

        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += " ORDER BY t.executed_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        async with db.execute(query, params) as cur:
            rows = await cur.fetchall()

        trades = []
        for r in rows:
            import json
            signal_data = json.loads(r[13]) if r[13] else {}
            trades.append({
                "id": r[0], "strategy_id": r[1], "strategy_name": r[2],
                "symbol": r[3], "market": r[4], "name": r[5],
                "side": r[6], "price": r[7], "shares": r[8],
                "notional": r[9], "commission": r[10], "slippage": r[11],
                "pnl": r[12], "signal_data": signal_data, "executed_at": r[14],
            })

        # 总数
        count_query = "SELECT COUNT(*) FROM trades"
        count_params = []
        if conditions:
            count_query += " WHERE " + " AND ".join(conditions[:len(params)-2])
            count_params = params[:len(params)-2]
        async with db.execute(count_query, count_params) as cur:
            total = (await cur.fetchone())[0]

        return {"trades": trades, "total": total, "limit": limit, "offset": offset}
    finally:
        await db.close()
