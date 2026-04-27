"""通知配置 API"""
import json
from typing import Optional

import jwt
from fastapi import APIRouter, Depends, HTTPException, Header
from pydantic import BaseModel

from config import JWT_SECRET
from database import get_db

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


async def get_current_user(authorization: Optional[str] = Header(None)) -> int:
    """获取当前用户ID（JWT认证）"""
    if not authorization:
        raise HTTPException(status_code=401, detail="未登录")

    try:
        token = authorization.replace("Bearer ", "") if authorization.startswith("Bearer ") else authorization
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        user_id = payload.get("user_id")
        if not user_id:
            raise HTTPException(status_code=401, detail="无效Token")
        return user_id
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token已过期")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="无效Token")


class NotificationConfigRequest(BaseModel):
    channel: str  # telegram, wechat, email
    config: dict  # {"bot_token": "...", "chat_id": "..."} 或 {"webhook_url": "..."} 或 {"email": "..."}
    is_enabled: bool = True


@router.get("/config")
async def get_notification_config(user_id: int = Depends(get_current_user)):
    """获取用户通知配置"""
    db = await get_db()
    try:
        async with db.execute(
            "SELECT channel, is_enabled, config_json FROM notification_config WHERE user_id=?",
            (user_id,)
        ) as cur:
            rows = await cur.fetchall()

        configs = []
        for row in rows:
            configs.append({
                "channel": row[0],
                "is_enabled": bool(row[1]),
                "config": json.loads(row[2]) if row[2] else {},
            })
        return {"configs": configs}
    finally:
        await db.close()


@router.post("/config")
async def update_notification_config(
    req: NotificationConfigRequest,
    user_id: int = Depends(get_current_user)
):
    """更新通知配置"""
    db = await get_db()
    try:
        # 检查是否已存在
        async with db.execute(
            "SELECT id FROM notification_config WHERE user_id=? AND channel=?",
            (user_id, req.channel)
        ) as cur:
            existing = await cur.fetchone()

        config_json = json.dumps(req.config, ensure_ascii=False)

        if existing:
            await db.execute(
                "UPDATE notification_config SET config_json=?, is_enabled=?, updated_at=datetime('now') WHERE user_id=? AND channel=?",
                (config_json, int(req.is_enabled), user_id, req.channel)
            )
        else:
            await db.execute(
                "INSERT INTO notification_config (user_id, channel, config_json, is_enabled) VALUES (?, ?, ?, ?)",
                (user_id, req.channel, config_json, int(req.is_enabled))
            )
        await db.commit()

        return {"status": "ok", "channel": req.channel}
    finally:
        await db.close()


@router.delete("/config/{channel}")
async def delete_notification_config(
    channel: str,
    user_id: int = Depends(get_current_user)
):
    """删除通知配置"""
    db = await get_db()
    try:
        await db.execute(
            "DELETE FROM notification_config WHERE user_id=? AND channel=?",
            (user_id, channel)
        )
        await db.commit()
        return {"status": "ok"}
    finally:
        await db.close()


@router.post("/test/{channel}")
async def test_notification(
    channel: str,
    user_id: int = Depends(get_current_user)
):
    """测试通知发送"""
    db = await get_db()
    try:
        async with db.execute(
            "SELECT config_json FROM notification_config WHERE user_id=? AND channel=? AND is_enabled=1",
            (user_id, channel)
        ) as cur:
            row = await cur.fetchone()

        if not row:
            raise HTTPException(status_code=404, detail="通知配置不存在或未启用")

        config = json.loads(row[0]) if row[0] else {}

        # 发送测试消息
        from services.notifier import Notifier
        if channel == "telegram":
            success = await Notifier.send_telegram(
                config.get("bot_token", ""),
                config.get("chat_id", ""),
                "📊 测试通知\n\n这是一条测试消息，通知配置正常工作！"
            )
        elif channel == "wechat":
            success = await Notifier.send_wechat(
                config.get("webhook_url", ""),
                "📊 测试通知\n\n这是一条测试消息，通知配置正常工作！"
            )
        elif channel == "email":
            success = await Notifier.send_email(
                config.get("smtp_server", "smtp.gmail.com"),
                config.get("smtp_port", 587),
                config.get("smtp_user", ""),
                config.get("smtp_password", ""),
                config.get("to_email", ""),
                "📊 测试通知",
                "这是一条测试消息，通知配置正常工作！"
            )
        else:
            raise HTTPException(status_code=400, detail="不支持的通知渠道")

        return {"status": "ok" if success else "failed", "channel": channel}
    finally:
        await db.close()