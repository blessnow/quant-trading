"""手机号注册/登录 API"""
import json
import uuid
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from loguru import logger

from database import get_db
from auth import hash_password, verify_password
from api.wechat_auth import _create_token, verify_token
from services.sms import send_sms, verify_code
import config

router = APIRouter(prefix="/api/auth", tags=["auth"])


class SendSMSRequest(BaseModel):
    phone: str


class PhoneRegisterRequest(BaseModel):
    phone: str
    code: str
    password: Optional[str] = None
    nickname: Optional[str] = None


class PhoneLoginRequest(BaseModel):
    phone: str
    code: Optional[str] = None
    password: Optional[str] = None


@router.post("/send-sms")
async def send_sms_api(req: SendSMSRequest):
    """发送验证码短信"""
    if not req.phone or len(req.phone) != 11:
        raise HTTPException(status_code=400, detail="手机号格式错误")

    result = await send_sms(req.phone)
    if not result["success"]:
        raise HTTPException(status_code=500, detail=result.get("detail", "发送失败"))

    resp = {"success": True, "expire_in": result["expire_in"]}
    if config.SMS_PROVIDER == "mock":
        resp["test_code"] = "123456"
    return resp


@router.post("/register-phone")
async def register_phone(req: PhoneRegisterRequest):
    """手机号注册"""
    if not verify_code(req.phone, req.code):
        raise HTTPException(status_code=400, detail="验证码错误或已过期")

    db = await get_db()
    try:
        async with db.execute("SELECT id FROM users WHERE phone=?", (req.phone,)) as cur:
            if await cur.fetchone():
                raise HTTPException(status_code=400, detail="手机号已注册")

        password_hash = hash_password(req.password) if req.password else None
        nickname = req.nickname or f"用户{req.phone[-4:]}"
        phone_openid = f"phone_{req.phone}"

        await db.execute(
            "INSERT INTO users (openid, phone, password_hash, login_type, nickname) VALUES (?, ?, ?, 'phone', ?)",
            (phone_openid, req.phone, password_hash, nickname)
        )
        await db.commit()

        async with db.execute("SELECT id FROM users WHERE phone=?", (req.phone,)) as cur:
            user = await cur.fetchone()

        token = _create_token(user[0], f"phone_{req.phone}")

        return {
            "token": token,
            "user_id": user[0],
            "nickname": nickname,
            "is_member": False,
            "member_expire_at": None,
        }
    finally:
        await db.close()


@router.post("/login-phone")
async def login_phone(req: PhoneLoginRequest):
    """手机号登录（验证码或密码）"""
    if not req.code and not req.password:
        raise HTTPException(status_code=400, detail="请输入验证码或密码")

    db = await get_db()
    try:
        async with db.execute(
            "SELECT id, password_hash, nickname, is_member, is_admin, member_expire_at FROM users WHERE phone=?",
            (req.phone,)
        ) as cur:
            user = await cur.fetchone()

        if not user:
            raise HTTPException(status_code=400, detail="用户不存在")

        user_id, password_hash, nickname, is_member, is_admin, member_expire = user

        if req.password:
            if not password_hash or not verify_password(req.password, password_hash):
                raise HTTPException(status_code=400, detail="密码错误")
        elif req.code:
            if not verify_code(req.phone, req.code):
                raise HTTPException(status_code=400, detail="验证码错误或已过期")

        await db.execute(
            "UPDATE users SET last_login_at = datetime('now') WHERE id=?",
            (user_id,)
        )
        await db.commit()

        token = _create_token(user_id, f"phone_{req.phone}")

        return {
            "token": token,
            "user_id": user_id,
            "nickname": nickname,
            "is_member": bool(is_member),
            "is_admin": bool(is_admin),
            "member_expire_at": member_expire,
        }
    finally:
        await db.close()


@router.post("/bind-phone")
async def bind_phone(phone: str, code: str, authorization: Optional[str] = None):
    """绑定手机号（微信用户）"""
    payload = verify_token(authorization)
    if not payload:
        raise HTTPException(status_code=401, detail="未登录")

    if not verify_code(phone, code):
        raise HTTPException(status_code=400, detail="验证码错误或已过期")

    db = await get_db()
    try:
        async with db.execute("SELECT id FROM users WHERE phone=? AND id!=?", (phone, payload["user_id"])) as cur:
            if await cur.fetchone():
                raise HTTPException(status_code=400, detail="手机号已被其他账号绑定")

        await db.execute(
            "UPDATE users SET phone=?, login_type='both' WHERE id=?",
            (phone, payload["user_id"])
        )
        await db.commit()

        return {"success": True}
    finally:
        await db.close()
