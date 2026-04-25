"""Web端微信扫码登录 API"""
import hashlib
import hmac
import json
import time
import uuid
from typing import Optional

import httpx
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from loguru import logger

from database import get_db
from api.wechat_auth import _create_token
import config

router = APIRouter(prefix="/api/auth", tags=["auth"])

# 内存存储登录会话（生产环境应使用Redis）
_login_sessions: dict[str, dict] = {}


def _generate_session_id() -> str:
    return uuid.uuid4().hex[:32]


@router.get("/qrcode")
async def get_qrcode():
    """生成登录二维码"""
    session_id = _generate_session_id()
    expires_at = time.time() + config.LOGIN_QR_EXPIRE_SECONDS

    if config.WX_WEB_APPID:
        # 正式模式：生成微信开放平台二维码
        state = session_id
        qr_url = (
            f"https://open.weixin.qq.com/connect/qrconnect"
            f"?appid={config.WX_WEB_APPID}"
            f"&redirect_uri={config.WX_WEB_REDIRECT_URI}"
            f"&response_type=code"
            f"&scope=snsapi_login"
            f"&state={state}"
        )
    else:
        # 测试模式：生成模拟二维码
        qr_url = f"https://api.qrserver.com/v1/create-qr-code/?size=200x200&data=login_{session_id}"
        logger.info(f"[登录] 测试模式，模拟二维码: {session_id}")

    # 存储会话
    _login_sessions[session_id] = {
        "status": "pending",
        "user_id": None,
        "token": None,
        "expires_at": expires_at,
    }

    return {
        "session_id": session_id,
        "qr_code_url": qr_url,
        "expires_in": config.LOGIN_QR_EXPIRE_SECONDS,
    }


@router.get("/check-login")
async def check_login(session_id: str):
    """轮询检查登录状态"""
    session = _login_sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")

    if session["expires_at"] < time.time():
        return {"status": "expired"}

    if session["status"] == "confirmed":
        # 返回登录结果，清理会话
        result = {
            "status": "confirmed",
            "token": session["token"],
            "user_id": session["user_id"],
        }
        # 不立即删除，让前端能多次轮询到结果
        return result

    return {"status": session["status"]}


@router.get("/callback")
async def login_callback(code: str, state: str):
    """微信扫码回调"""
    session_id = state
    session = _login_sessions.get(session_id)
    if not session or session["expires_at"] < time.time():
        raise HTTPException(status_code=400, detail="登录已过期")

    if config.WX_WEB_APPID:
        # 正式模式：用code换取access_token和openid
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    "https://api.weixin.qq.com/sns/oauth2/access_token",
                    params={
                        "appid": config.WX_WEB_APPID,
                        "secret": config.WX_WEB_SECRET,
                        "code": code,
                        "grant_type": "authorization_code",
                    },
                    timeout=10,
                )
                data = resp.json()

            if "errcode" in data:
                logger.error(f"[登录] 微信回调失败: {data}")
                session["status"] = "failed"
                return {"error": data.get("errmsg", "登录失败")}

            web_openid = data["openid"]
            unionid = data.get("unionid")
            access_token = data["access_token"]

            # 获取用户信息
            user_info_resp = await client.get(
                "https://api.weixin.qq.com/sns/userinfo",
                params={"access_token": access_token, "openid": web_openid},
                timeout=10,
            )
            user_info = user_info_resp.json()
            nickname = user_info.get("nickname", "")
            avatar_url = user_info.get("headimgurl", "")

        except Exception as e:
            logger.error(f"[登录] 微信API异常: {e}")
            session["status"] = "failed"
            return {"error": "登录失败"}
    else:
        # 测试模式：模拟登录成功
        web_openid = f"web_test_{session_id}"
        unionid = None
        nickname = f"用户{session_id[:6]}"
        avatar_url = ""
        logger.info(f"[登录] 测试模式，模拟登录成功: {web_openid}")

    db = await get_db()
    try:
        # 查找或创建用户
        async with db.execute(
            "SELECT id, is_member, member_expire_at FROM users WHERE web_openid=?",
            (web_openid,)
        ) as cur:
            user = await cur.fetchone()

        if user:
            user_id = user[0]
            is_member = bool(user[1])
            member_expire = user[2]
        else:
            # 创建新用户
            await db.execute(
                "INSERT INTO users (web_openid, unionid, login_type, nickname, avatar_url) VALUES (?, ?, 'web_qr', ?, ?)",
                (web_openid, unionid, nickname, avatar_url)
            )
            await db.commit()
            async with db.execute("SELECT id FROM users WHERE web_openid=?", (web_openid,)) as cur:
                user = await cur.fetchone()
            user_id = user[0]
            is_member = False
            member_expire = None

        # 生成token
        token = _create_token(user_id, web_openid)

        # 更新会话
        session["status"] = "confirmed"
        session["user_id"] = user_id
        session["token"] = token

        return {"status": "success", "user_id": user_id}
    finally:
        await db.close()


@router.post("/confirm-test-login")
async def confirm_test_login(session_id: str):
    """测试模式：确认登录（用于前端测试）"""
    session = _login_sessions.get(session_id)
    if not session or session["expires_at"] < time.time():
        raise HTTPException(status_code=400, detail="登录已过期")

    if config.WX_WEB_APPID:
        raise HTTPException(status_code=400, detail="非测试模式")

    # 模拟登录成功
    web_openid = f"web_test_{session_id}"

    db = await get_db()
    try:
        async with db.execute("SELECT id, is_member, member_expire_at FROM users WHERE web_openid=?", (web_openid,)) as cur:
            user = await cur.fetchone()

        if user:
            user_id = user[0]
            is_member = bool(user[1])
            member_expire = user[2]
        else:
            await db.execute(
                "INSERT INTO users (web_openid, login_type, nickname) VALUES (?, 'web_qr', ?)",
                (web_openid, f"用户{session_id[:6]}")
            )
            await db.commit()
            async with db.execute("SELECT id FROM users WHERE web_openid=?", (web_openid,)) as cur:
                user = await cur.fetchone()
            user_id = user[0]
            is_member = False
            member_expire = None

        token = _create_token(user_id, web_openid)

        session["status"] = "confirmed"
        session["user_id"] = user_id
        session["token"] = token

        return {
            "status": "confirmed",
            "token": token,
            "user_id": user_id,
            "is_member": is_member,
            "member_expire_at": member_expire,
        }
    finally:
        await db.close()


@router.post("/logout")
async def logout():
    """登出"""
    return {"success": True}
