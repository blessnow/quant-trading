"""短信发送服务 — 支持阿里云短信 / mock模式

验证码存 SQLite（sms_verification_codes），避免进程内存导致多 Worker / 多副本
下发与校验命中不同实例时永远校验失败（密码登录不受影响）。
多副本且各副本独立磁盘时仍需 Redis 等共享存储；单副本 + 共享 DB 文件即可。
"""
import json
import random
import time
from typing import Optional

from loguru import logger

import config


def generate_code() -> str:
    return f"{random.randint(0, 999999):06d}"


async def store_code(phone: str, code: str, ttl: int = 300) -> None:
    from database import get_db

    exp = time.time() + ttl
    db = await get_db()
    try:
        await db.execute(
            """INSERT INTO sms_verification_codes (phone, code, expires_at)
               VALUES (?, ?, ?)
               ON CONFLICT(phone) DO UPDATE SET
                 code=excluded.code,
                 expires_at=excluded.expires_at""",
            (phone, code, exp),
        )
        await db.commit()
    finally:
        await db.close()


async def verify_code(phone: str, code: str) -> bool:
    from database import get_db

    if (
        config.SMS_FIXED_TEST_CODE
        and code == config.SMS_FIXED_TEST_CODE
        and phone in config.SMS_FIXED_TEST_PHONES
    ):
        logger.info(f"[短信] 固定测试验证码通过: {phone}")
        db = await get_db()
        try:
            await db.execute("DELETE FROM sms_verification_codes WHERE phone=?", (phone,))
            await db.commit()
        finally:
            await db.close()
        return True

    db = await get_db()
    try:
        async with db.execute(
            "SELECT code, expires_at FROM sms_verification_codes WHERE phone=?",
            (phone,),
        ) as cur:
            row = await cur.fetchone()
        if not row:
            return False
        stored, expires_at = row[0], float(row[1])
        if time.time() > expires_at:
            await db.execute("DELETE FROM sms_verification_codes WHERE phone=?", (phone,))
            await db.commit()
            return False
        if stored != code:
            return False
        await db.execute("DELETE FROM sms_verification_codes WHERE phone=?", (phone,))
        await db.commit()
        return True
    finally:
        await db.close()


async def send_sms(phone: str, code: Optional[str] = None) -> dict:
    """
    发送验证码短信。
    返回 {"success": bool, "detail": str, "expire_in": int}
    """
    code = code or generate_code()
    ttl = 300

    if config.SMS_PROVIDER == "mock":
        await store_code(phone, code, ttl)
        logger.info(f"[短信-mock] {phone} -> {code}")
        return {"success": True, "expire_in": ttl}

    if config.SMS_PROVIDER == "aliyun":
        return await _send_aliyun(phone, code, ttl)

    return {"success": False, "detail": f"未知短信服务商: {config.SMS_PROVIDER}"}


async def _send_aliyun(phone: str, code: str, ttl: int) -> dict:
    """阿里云短信发送"""
    try:
        from alibabacloud_dysmsapi20170525.client import Client
        from alibabacloud_dysmsapi20170525 import models as sms_models
        from alibabacloud_tea_openapi import models as open_api_models

        if not config.SMS_ACCESS_KEY or not config.SMS_SECRET_KEY:
            logger.error("[短信-阿里云] ACCESS_KEY / SECRET_KEY 未配置")
            return {"success": False, "detail": "短信服务未配置"}

        conf = open_api_models.Config(
            access_key_id=config.SMS_ACCESS_KEY,
            access_key_secret=config.SMS_SECRET_KEY,
        )
        conf.endpoint = "dysmsapi.aliyuncs.com"
        client = Client(conf)

        template_params = json.dumps({"code": code}, ensure_ascii=False)

        request = sms_models.SendSmsRequest(
            phone_numbers=phone,
            sign_name=config.SMS_SIGN_NAME,
            template_code=config.SMS_TEMPLATE_CODE,
            template_param=template_params,
        )
        resp = await client.send_sms_async(request)

        if resp.body.code == "OK":
            await store_code(phone, code, ttl)
            logger.info(f"[短信-阿里云] 发送成功: {phone}")
            return {"success": True, "expire_in": ttl}
        else:
            logger.error(f"[短信-阿里云] 发送失败: {resp.body.code} {resp.body.message}")
            return {"success": False, "detail": resp.body.message}

    except ImportError:
        logger.error("[短信-阿里云] SDK未安装，请运行: pip install alibabacloud-dysmsapi20170525")
        return {"success": False, "detail": "短信SDK未安装"}
    except Exception as e:
        logger.error(f"[短信-阿里云] 异常: {e}")
        return {"success": False, "detail": "短信发送异常"}
