"""微信支付 API"""
import time
import uuid
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from loguru import logger

from database import get_db
from api.wechat_auth import get_current_user
from wechat.pay import create_prepay_order, create_native_order, verify_notify
import config

router = APIRouter(prefix="/api/pay", tags=["pay"])

PLANS = {
    "monthly": {"price": config.MEMBER_PRICE_MONTHLY, "days": 30, "label": "月度会员"},
    "yearly": {"price": config.MEMBER_PRICE_YEARLY, "days": 365, "label": "年度会员"},
}

# 内存存储支付会话（生产环境应使用Redis）
_payment_sessions: dict[str, dict] = {}


class CreateOrderRequest(BaseModel):
    plan: str  # monthly or yearly


class CreateNativeOrderRequest(BaseModel):
    plan: str


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
    """微信支付 APIv3 回调（JSON + 应答 JSON）"""
    raw = await request.body()
    text = raw.decode("utf-8")
    hdrs = {k.lower(): v for k, v in request.headers.items()}
    data = await verify_notify(text, hdrs)
    if not data:
        return JSONResponse(
            status_code=401,
            content={"code": "FAIL", "message": "验签或解密失败"},
        )

    if data.get("result_code") != "SUCCESS":
        return JSONResponse(
            status_code=400,
            content={"code": "FAIL", "message": "支付未成功"},
        )

    order_no = data.get("out_trade_no")
    trade_no = data.get("transaction_id")

    db = await get_db()
    try:
        async with db.execute(
            "SELECT id, user_id, plan, status FROM orders WHERE order_no=?",
            (order_no,),
        ) as cur:
            order = await cur.fetchone()
        if not order or order[3] == "paid":
            return JSONResponse(content={"code": "SUCCESS", "message": "成功"})

        plan_info = PLANS.get(order[2], PLANS["monthly"])
        expire = datetime.now() + timedelta(days=plan_info["days"])

        await db.execute(
            "UPDATE orders SET status='paid', paid_at=datetime('now'), trade_no=? WHERE id=?",
            (trade_no, order[0]),
        )
        await db.execute(
            "UPDATE users SET is_member=1, member_expire_at=? WHERE id=?",
            (expire.strftime("%Y-%m-%d %H:%M:%S"), order[1]),
        )
        await db.commit()
    finally:
        await db.close()

    return JSONResponse(content={"code": "SUCCESS", "message": "成功"})


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


# ============ Web端Native支付接口 ============

@router.post("/create-native-order")
async def create_native_order_api(req: CreateNativeOrderRequest, authorization: Optional[str] = Header(None)):
    """创建Native扫码支付订单（Web端）"""
    user = await get_current_user(authorization)
    plan = PLANS.get(req.plan)
    if not plan:
        raise HTTPException(status_code=400, detail="无效套餐")

    db = await get_db()
    try:
        # 创建订单
        order_no = f"QT{int(time.time())}{uuid.uuid4().hex[:6]}"
        amount_fen = int(plan["price"] * 100)

        await db.execute(
            "INSERT INTO orders (user_id, order_no, plan, amount, status) VALUES (?, ?, ?, ?, 'pending')",
            (user["user_id"], order_no, req.plan, plan["price"])
        )
        await db.commit()

        # 调用Native支付下单
        result = await create_native_order(
            order_no=order_no,
            amount_fen=amount_fen,
            description=f"QuantTrader {plan['label']}",
        )
        if not result:
            raise HTTPException(status_code=500, detail="创建支付订单失败")

        # 创建支付会话
        session_id = uuid.uuid4().hex[:32]
        expires_at = time.time() + config.PAY_QR_EXPIRE_SECONDS
        _payment_sessions[session_id] = {
            "order_no": order_no,
            "user_id": user["user_id"],
            "status": "pending",
            "expires_at": expires_at,
        }

        return {
            "session_id": session_id,
            "order_no": order_no,
            "qr_code_url": result["code_url"],
            "amount": plan["price"],
            "expires_in": config.PAY_QR_EXPIRE_SECONDS,
            "test_mode": result.get("test_mode", False),
        }
    finally:
        await db.close()


@router.get("/check-payment")
async def check_payment(session_id: str):
    """轮询检查支付状态"""
    session = _payment_sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")

    if session["expires_at"] < time.time():
        return {"status": "expired"}

    # 查询订单状态
    db = await get_db()
    try:
        async with db.execute(
            "SELECT status, plan FROM orders WHERE order_no=?",
            (session["order_no"],)
        ) as cur:
            order = await cur.fetchone()

        if not order:
            return {"status": "not_found"}

        if order[0] == "paid":
            # 更新会话状态
            session["status"] = "paid"

            # 获取会员到期时间
            async with db.execute(
                "SELECT member_expire_at FROM users WHERE id=?",
                (session["user_id"],)
            ) as cur:
                user = await cur.fetchone()

            return {
                "status": "paid",
                "member_expire_at": user[0] if user else None,
            }

        return {"status": "pending"}
    finally:
        await db.close()


@router.post("/confirm-native-test")
async def confirm_native_test(session_id: str):
    """测试模式：确认Native支付"""
    session = _payment_sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")

    if session["expires_at"] < time.time():
        raise HTTPException(status_code=400, detail="支付已过期")

    if config.WX_MCH_ID:
        raise HTTPException(status_code=400, detail="非测试模式")

    db = await get_db()
    try:
        # 更新订单
        async with db.execute(
            "SELECT id, plan FROM orders WHERE order_no=?",
            (session["order_no"],)
        ) as cur:
            order = await cur.fetchone()
        if not order:
            raise HTTPException(status_code=404, detail="订单不存在")

        order_id, plan = order
        plan_info = PLANS.get(plan, PLANS["monthly"])
        expire = datetime.now() + timedelta(days=plan_info["days"])

        await db.execute(
            "UPDATE orders SET status='paid', paid_at=datetime('now'), trade_no=? WHERE id=?",
            (f"test_{session['order_no']}", order_id)
        )
        await db.execute(
            "UPDATE users SET is_member=1, member_expire_at=? WHERE id=?",
            (expire.strftime("%Y-%m-%d %H:%M:%S"), session["user_id"])
        )
        await db.commit()

        # 更新会话
        session["status"] = "paid"

        return {
            "success": True,
            "member_expire_at": expire.strftime("%Y-%m-%d %H:%M:%S"),
        }
    finally:
        await db.close()


@router.get("/check-status")
async def check_order_status(order_no: str, authorization: Optional[str] = Header(None)):
    """查询订单支付状态（小程序用）"""
    user = await get_current_user(authorization)
    db = await get_db()
    try:
        async with db.execute(
            "SELECT status, plan FROM orders WHERE order_no=? AND user_id=?",
            (order_no, user["user_id"])
        ) as cur:
            order = await cur.fetchone()

        if not order:
            raise HTTPException(status_code=404, detail="订单不存在")

        if order[0] == "paid":
            async with db.execute(
                "SELECT member_expire_at FROM users WHERE id=?",
                (user["user_id"],)
            ) as cur:
                user_row = await cur.fetchone()
            return {
                "status": "paid",
                "member_expire_at": user_row[0] if user_row else None,
            }

        return {"status": order[0]}
    finally:
        await db.close()
