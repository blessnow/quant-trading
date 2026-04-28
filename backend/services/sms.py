"""短信发送服务 — 支持阿里云短信 / mock模式"""
import json
import random
import time
from typing import Optional

from loguru import logger

import config

_code_store: dict[str, tuple[str, float]] = {}


def generate_code() -> str:
    return f"{random.randint(0, 999999):06d}"


def store_code(phone: str, code: str, ttl: int = 300) -> None:
    _code_store[phone] = (code, time.time() + ttl)


def verify_code(phone: str, code: str) -> bool:
    entry = _code_store.get(phone)
    if not entry:
        return False
    stored_code, expires_at = entry
    if time.time() > expires_at:
        _code_store.pop(phone, None)
        return False
    if stored_code != code:
        return False
    _code_store.pop(phone, None)
    return True


async def send_sms(phone: str, code: Optional[str] = None) -> dict:
    """
    发送验证码短信。
    返回 {"success": bool, "detail": str, "expire_in": int}
    """
    code = code or generate_code()
    ttl = 300

    if config.SMS_PROVIDER == "mock":
        store_code(phone, code, ttl)
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
            store_code(phone, code, ttl)
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
