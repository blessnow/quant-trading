"""微信OAuth登录"""
import httpx
from loguru import logger

import config


async def code2session(code: str) -> dict:
    """用code换取openid和session_key"""
    url = "https://api.weixin.qq.com/sns/jscode2session"
    params = {
        "appid": config.WX_APPID,
        "secret": config.WX_SECRET,
        "js_code": code,
        "grant_type": "authorization_code",
    }
    async with httpx.AsyncClient() as client:
        resp = await client.get(url, params=params, timeout=10)
        data = resp.json()

    if "errcode" in data and data["errcode"] != 0:
        logger.error(f"[微信登录] code2session失败: {data}")
        return {}

    return {
        "openid": data.get("openid", ""),
        "session_key": data.get("session_key", ""),
        "unionid": data.get("unionid", ""),
    }


async def get_access_token() -> str:
    """获取小程序全局access_token（用于模板消息等）"""
    url = "https://api.weixin.qq.com/cgi-bin/token"
    params = {
        "grant_type": "client_credential",
        "appid": config.WX_APPID,
        "secret": config.WX_SECRET,
    }
    async with httpx.AsyncClient() as client:
        resp = await client.get(url, params=params, timeout=10)
        data = resp.json()
    return data.get("access_token", "")
