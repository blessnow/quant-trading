"""微信认证+用户管理 API"""
import hashlib
import hmac
import json
import time
import uuid
from typing import Optional

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from database import get_db
from wechat.auth import code2session
import config

router = APIRouter(prefix="/api/wechat", tags=["wechat"])


def _create_token(user_id: int, openid: str) -> str:
    """简单JWT生成"""
    payload = {
        "user_id": user_id,
        "openid": openid,
        "exp": int(time.time()) + config.JWT_EXPIRE_HOURS * 3600,
        "jti": uuid.uuid4().hex[:16],
    }
    # 简单签名：base64(payload) + HMAC
    payload_str = json.dumps(payload, separators=(",", ":"))
    sig = hmac.new(config.JWT_SECRET.encode(), payload_str.encode(), hashlib.sha256).hexdigest()[:32]
    import base64
    token = base64.urlsafe_b64encode(payload_str.encode()).decode() + "." + sig
    return token


def verify_token(authorization: str) -> Optional[dict]:
    """验证JWT token，返回payload或None"""
    try:
        if not authorization or not authorization.startswith("Bearer "):
            return None
        token = authorization[7:]
        parts = token.split(".")
        if len(parts) != 2:
            return None
        import base64
        payload_str = base64.urlsafe_b64decode(parts[0]).decode()
        sig = hmac.new(config.JWT_SECRET.encode(), payload_str.encode(), hashlib.sha256).hexdigest()[:32]
        if sig != parts[1]:
            return None
        payload = json.loads(payload_str)
        if payload.get("exp", 0) < time.time():
            return None
        return payload
    except Exception:
        return None


async def get_current_user(authorization: Optional[str] = Header(None)) -> dict:
    """FastAPI依赖：获取当前用户"""
    if not authorization:
        raise HTTPException(status_code=401, detail="未登录")
    payload = verify_token(authorization)
    if not payload:
        raise HTTPException(status_code=401, detail="登录已过期")
    return payload


class LoginRequest(BaseModel):
    code: str


@router.post("/login")
async def login(req: LoginRequest):
    """微信小程序登录"""
    session = await code2session(req.code)
    openid = session.get("openid", "")
    if not openid:
        # 测试模式：用code作为openid
        openid = f"test_{req.code}" if config.WX_APPID == "wx_test_appid" else ""
        if not openid:
            raise HTTPException(status_code=400, detail="登录失败")

    db = await get_db()
    try:
        # 查找或创建用户
        async with db.execute("SELECT id, is_member, is_admin, member_expire_at FROM users WHERE openid=?", (openid,)) as cur:
            user = await cur.fetchone()

        if user:
            user_id = user[0]
            is_member = bool(user[1])
            is_admin = bool(user[2])
            member_expire = user[3]
        else:
            import asyncio
            await db.execute(
                "INSERT INTO users (openid, nickname) VALUES (?, ?)",
                (openid, f"用户{openid[-6:]}")
            )
            await db.commit()
            async with db.execute("SELECT id FROM users WHERE openid=?", (openid,)) as cur:
                user = await cur.fetchone()
            user_id = user[0]
            is_member = False
            is_admin = False
            member_expire = None

        token = _create_token(user_id, openid)

        return {
            "token": token,
            "user_id": user_id,
            "is_member": is_member,
            "is_admin": is_admin,
            "member_expire_at": member_expire,
        }
    finally:
        await db.close()


@router.get("/profile")
async def get_profile(authorization: Optional[str] = Header(None)):
    """获取用户信息"""
    user = await get_current_user(authorization)
    db = await get_db()
    try:
        async with db.execute(
            "SELECT id, openid, nickname, avatar_url, is_member, member_expire_at, created_at FROM users WHERE id=?",
            (user["user_id"],)
        ) as cur:
            row = await cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="用户不存在")
        return {
            "id": row[0],
            "nickname": row[1],
            "avatar_url": row[2],
            "is_member": bool(row[3]),
            "member_expire_at": row[4],
            "created_at": row[5],
        }
    finally:
        await db.close()


# 统一认证接口（供前端使用）
@router.get("/me")
async def get_me(authorization: Optional[str] = Header(None)):
    """获取当前用户完整信息"""
    user = await get_current_user(authorization)
    db = await get_db()
    try:
        async with db.execute(
            "SELECT id, openid, phone, nickname, avatar_url, is_member, is_admin, member_expire_at, login_type, created_at FROM users WHERE id=?",
            (user["user_id"],)
        ) as cur:
            row = await cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="用户不存在")
        return {
            "id": row[0],
            "openid": row[1],
            "phone": row[2],
            "nickname": row[3],
            "avatar_url": row[4],
            "is_member": bool(row[5]),
            "is_admin": bool(row[6]),
            "member_expire_at": row[7],
            "login_type": row[8],
            "created_at": row[9],
        }
    finally:
        await db.close()


class RefreshRequest(BaseModel):
    token: str


@router.post("/refresh")
async def refresh_token(req: RefreshRequest):
    """刷新Token"""
    payload = verify_token(req.token)
    if not payload:
        raise HTTPException(status_code=401, detail="Token无效")

    db = await get_db()
    try:
        async with db.execute(
            "SELECT openid, is_member, member_expire_at FROM users WHERE id=?",
            (payload["user_id"],)
        ) as cur:
            user = await cur.fetchone()
        if not user:
            raise HTTPException(status_code=404, detail="用户不存在")

        new_token = _create_token(payload["user_id"], user[0] or f"user_{payload['user_id']}")
        return {
            "token": new_token,
            "is_member": bool(user[1]),
            "member_expire_at": user[2],
        }
    finally:
        await db.close()
