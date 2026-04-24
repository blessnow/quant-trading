"""微信支付 API"""
import time
import uuid
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel

from database import get_db
from api.wechat_auth import get_current_user
from wechat.pay import create_prepay_order, verify_notify
import config

router = APIRouter(prefix="/api/pay", tags=["pay"])

PLANS = {
    "monthly": {"price": config.MEMBER_PRICE_MONTHLY, "days": 30, "label": "月度会员"},
    "yearly": {"price": config.MEMBER_PRICE_YEARLY, "days": 365, "label": "年度会员"},
}


class CreateOrderRequest(BaseModel):
    plan: str  # monthly or yearly


@router.post("/create-order")
async def create_order(req: CreateOrderRequest, authorization: Optional[str] = Header(None)):
    """创建会员订单"""
    user = await get_current_user(authorization)
    plan = PLANS.get(req.plan)
    if not plan:
        raise HTTPException(status_code=400, detail="无效套餐")

    db = await get_db()
    try:
        order_no = f"QT{int(time.time())}{uuid.uuid4().hex[:6]}"
        amount_fen = int(plan["price"] * 100)

        await db.execute(
            "INSERT INTO orders (user_id, order_no, plan, amount, status) VALUES (?, ?, ?, ?, 'pending')",
            (user["user_id"], order_no, req.plan, plan["price"])
        )
        await db.commit()

        # 测试模式直接激活
        if config.WX_MCH_ID == "":
            return {
                "order_no": order_no,
                "amount": plan["price"],
                "plan": req.plan,
                "label": plan["label"],
                "test_mode": True,
                "message": "测试模式：点击确认即可激活会员",
            }

        pay_params = await create_prepay_order(
            openid=user["openid"],
            order_no=order_no,
            amount_fen=amount_fen,
            description=f"QuantTrader {plan['label']}",
        )
        if not pay_params:
            raise HTTPException(status_code=500, detail="创建支付订单失败")

        return {"order_no": order_no, "amount": plan["price"], "pay_params": pay_params}
    finally:
        await db.close()


@router.post("/confirm-test")
async def confirm_test_order(authorization: Optional[str] = Header(None)):
    """测试模式：确认订单激活会员"""
    user = await get_current_user(authorization)
    db = await get_db()
    try:
        # 找到最近的pending订单
        async with db.execute(
            "SELECT id, order_no, plan, amount FROM orders WHERE user_id=? AND status='pending' ORDER BY created_at DESC LIMIT 1",
            (user["user_id"],)
        ) as cur:
            order = await cur.fetchone()
        if not order:
            raise HTTPException(status_code=400, detail="无待支付订单")

        order_id, order_no, plan, amount = order
        plan_info = PLANS.get(plan, PLANS["monthly"])
        now = datetime.now()
        expire = now + timedelta(days=plan_info["days"])

        # 更新订单
        await db.execute(
            "UPDATE orders SET status='paid', paid_at=datetime('now'), trade_no=? WHERE id=?",
            (f"test_{order_no}", order_id)
        )
        # 更新会员
        await db.execute(
            "UPDATE users SET is_member=1, member_expire_at=? WHERE id=?",
            (expire.strftime("%Y-%m-%d %H:%M:%S"), user["user_id"])
        )
        await db.commit()

        return {
            "success": True,
            "member_expire_at": expire.strftime("%Y-%m-%d %H:%M:%S"),
            "plan": plan,
        }
    finally:
        await db.close()


@router.post("/notify")
async def pay_notify(request: Request):
    """微信支付回调"""
    body = await request.body()
    data = verify_notify(body.decode())
    if not data:
        return {"return_code": "FAIL", "return_msg": "签名验证失败"}

    if data.get("result_code") != "SUCCESS":
        return {"return_code": "FAIL", "return_msg": "支付失败"}

    order_no = data.get("out_trade_no")
    trade_no = data.get("transaction_id")

    db = await get_db()
    try:
        async with db.execute("SELECT id, user_id, plan FROM orders WHERE order_no=?", (order_no,)) as cur:
            order = await cur.fetchone()
        if not order or order[3] == "paid":
            return {"return_code": "SUCCESS", "return_msg": "OK"}

        plan_info = PLANS.get(order[2], PLANS["monthly"])
        expire = datetime.now() + timedelta(days=plan_info["days"])

        await db.execute("UPDATE orders SET status='paid', paid_at=datetime('now'), trade_no=? WHERE id=?", (trade_no, order[0]))
        await db.execute("UPDATE users SET is_member=1, member_expire_at=? WHERE id=?", (expire.strftime("%Y-%m-%d %H:%M:%S"), order[1]))
        await db.commit()
    finally:
        await db.close()

    return {"return_code": "SUCCESS", "return_msg": "OK"}


@router.get("/orders")
async def list_orders(authorization: Optional[str] = Header(None)):
    """用户订单列表"""
    user = await get_current_user(authorization)
    db = await get_db()
    try:
        async with db.execute(
            "SELECT order_no, plan, amount, status, paid_at, created_at FROM orders WHERE user_id=? ORDER BY created_at DESC LIMIT 20",
            (user["user_id"],)
        ) as cur:
            rows = await cur.fetchall()
        orders = [
            {"order_no": r[0], "plan": r[1], "amount": r[2], "status": r[3], "paid_at": r[4], "created_at": r[5]}
            for r in rows
        ]
        return {"orders": orders}
    finally:
        await db.close()
