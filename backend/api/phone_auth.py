"""手机号注册/登录 API"""
import hashlib
import json
import time
import uuid
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from loguru import logger

from database import get_db
from api.wechat_auth import _create_token, verify_token
import config

router = APIRouter(prefix="/api/auth", tags=["auth"])

# 内存存储验证码（生产环境应使用Redis）
_sms_codes: dict[str, tuple[str, float]] = {}


def _hash_password(password: str) -> str:
    """密码哈希"""
    return hashlib.sha256((password + config.JWT_SECRET).encode()).hexdigest()


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
async def send_sms(req: SendSMSRequest):
    """发送验证码（测试模式返回固定验证码123456）"""
    if not req.phone or len(req.phone) != 11:
        raise HTTPException(status_code=400, detail="手机号格式错误")

    # 测试模式：固定验证码
    if config.SMS_PROVIDER == "mock":
        code = "123456"
    else:
        # 生产模式：生成随机验证码
        code = str(uuid.uuid4().int)[:6]
        # TODO: 调用短信服务商API发送验证码
        logger.info(f"[短信] 发送验证码到 {req.phone}: {code}")

    # 存储验证码（5分钟有效）
    _sms_codes[req.phone] = (code, time.time() + 300)

    return {"success": True, "expire_in": 300, "test_code": code if config.SMS_PROVIDER == "mock" else None}


@router.post("/register-phone")
async def register_phone(req: PhoneRegisterRequest):
    """手机号注册"""
    # 验证验证码
    stored = _sms_codes.get(req.phone)
    if not stored or stored[1] < time.time():
        raise HTTPException(status_code=400, detail="验证码已过期")
    if stored[0] != req.code:
        raise HTTPException(status_code=400, detail="验证码错误")

    db = await get_db()
    try:
        # 检查手机号是否已注册
        async with db.execute("SELECT id FROM users WHERE phone=?", (req.phone,)) as cur:
            if await cur.fetchone():
                raise HTTPException(status_code=400, detail="手机号已注册")

        # 创建用户
        password_hash = _hash_password(req.password) if req.password else None
        nickname = req.nickname or f"用户{req.phone[-4:]}"
        # 为手机号用户生成唯一openid
        phone_openid = f"phone_{req.phone}"

        await db.execute(
            "INSERT INTO users (openid, phone, password_hash, login_type, nickname) VALUES (?, ?, ?, 'phone', ?)",
            (phone_openid, req.phone, password_hash, nickname)
        )
        await db.commit()

        # 获取用户ID
        async with db.execute("SELECT id FROM users WHERE phone=?", (req.phone,)) as cur:
            user = await cur.fetchone()

        # 删除验证码
        del _sms_codes[req.phone]

        # 生成token
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
        # 查找用户
        async with db.execute(
            "SELECT id, password_hash, nickname, is_member, member_expire_at FROM users WHERE phone=?",
            (req.phone,)
        ) as cur:
            user = await cur.fetchone()

        if not user:
            raise HTTPException(status_code=400, detail="用户不存在")

        user_id, password_hash, nickname, is_member, member_expire = user

        # 验证密码
        if req.password:
            if not password_hash or password_hash != _hash_password(req.password):
                raise HTTPException(status_code=400, detail="密码错误")
        # 验证验证码
        elif req.code:
            stored = _sms_codes.get(req.phone)
            if not stored or stored[1] < time.time():
                raise HTTPException(status_code=400, detail="验证码已过期")
            if stored[0] != req.code:
                raise HTTPException(status_code=400, detail="验证码错误")
            del _sms_codes[req.phone]

        # 更新最后登录时间
        await db.execute(
            "UPDATE users SET last_login_at = datetime('now') WHERE id=?",
            (user_id,)
        )
        await db.commit()

        # 生成token
        token = _create_token(user_id, f"phone_{req.phone}")

        return {
            "token": token,
            "user_id": user_id,
            "nickname": nickname,
            "is_member": bool(is_member),
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

    # 验证验证码
    stored = _sms_codes.get(phone)
    if not stored or stored[1] < time.time():
        raise HTTPException(status_code=400, detail="验证码已过期")
    if stored[0] != code:
        raise HTTPException(status_code=400, detail="验证码错误")

    db = await get_db()
    try:
        # 检查手机号是否已被其他用户绑定
        async with db.execute("SELECT id FROM users WHERE phone=? AND id!=?", (phone, payload["user_id"])) as cur:
            if await cur.fetchone():
                raise HTTPException(status_code=400, detail="手机号已被其他账号绑定")

        # 绑定手机号
        await db.execute(
            "UPDATE users SET phone=?, login_type='both' WHERE id=?",
            (phone, payload["user_id"])
        )
        await db.commit()

        del _sms_codes[phone]

        return {"success": True}
    finally:
        await db.close()
