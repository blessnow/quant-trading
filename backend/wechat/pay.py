"""微信支付工具"""
import hashlib
import time
import uuid
import xml.etree.ElementTree as ET
from typing import Optional

import httpx
from loguru import logger

import config


def _make_sign(params: dict, key: str) -> str:
    """微信支付签名"""
    sorted_params = sorted(params.items())
    sign_str = "&".join(f"{k}={v}" for k, v in sorted_params if v) + f"&key={key}"
    return hashlib.md5(sign_str.encode()).hexdigest().upper()


def _dict_to_xml(data: dict) -> str:
    xml = "<xml>"
    for k, v in data.items():
        xml += f"<{k}><![CDATA[{v}]]></{k}>"
    xml += "</xml>"
    return xml


def _xml_to_dict(xml_str: str) -> dict:
    root = ET.fromstring(xml_str)
    return {child.tag: child.text for child in root}


async def create_prepay_order(
    openid: str,
    order_no: str,
    amount_fen: int,
    description: str = "量化交易会员",
) -> Optional[dict]:
    """调用微信统一下单API，返回小程序支付参数（JSAPI模式）"""
    if not config.WX_MCH_ID:
        # 测试模式：直接返回模拟支付参数
        logger.info(f"[支付] 测试模式，模拟下单: {order_no} {amount_fen}分")
        return {
            "timeStamp": str(int(time.time())),
            "nonceStr": uuid.uuid4().hex[:32],
            "package": f"prepay_id=test_{order_no}",
            "signType": "MD5",
            "paySign": "test_sign",
        }

    nonce_str = uuid.uuid4().hex[:32]
    params = {
        "appid": config.WX_APPID,
        "mch_id": config.WX_MCH_ID,
        "nonce_str": nonce_str,
        "body": description,
        "out_trade_no": order_no,
        "total_fee": amount_fen,
        "spbill_create_ip": "127.0.0.1",
        "notify_url": config.WX_PAY_NOTIFY_URL,
        "trade_type": "JSAPI",
        "openid": openid,
    }
    params["sign"] = _make_sign(params, config.WX_MCH_KEY)

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "https://api.mch.weixin.qq.com/pay/unifiedorder",
                content=_dict_to_xml(params),
                headers={"Content-Type": "application/xml"},
                timeout=15,
            )
        result = _xml_to_dict(resp.text)

        if result.get("return_code") != "SUCCESS" or result.get("result_code") != "SUCCESS":
            logger.error(f"[支付] 统一下单失败: {result}")
            return None

        prepay_id = result["prepay_id"]
        # 生成小程序支付参数
        pay_params = {
            "appId": config.WX_APPID,
            "timeStamp": str(int(time.time())),
            "nonceStr": uuid.uuid4().hex[:32],
            "package": f"prepay_id={prepay_id}",
            "signType": "MD5",
        }
        pay_params["paySign"] = _make_sign(pay_params, config.WX_MCH_KEY)
        return pay_params

    except Exception as e:
        logger.error(f"[支付] 异常: {e}")
        return None


async def create_native_order(
    order_no: str,
    amount_fen: int,
    description: str = "量化交易会员",
) -> Optional[dict]:
    """调用微信统一下单API，返回Native支付二维码URL"""
    if not config.WX_MCH_ID:
        # 测试模式：返回模拟二维码URL
        logger.info(f"[支付-Native] 测试模式，模拟下单: {order_no} {amount_fen}分")
        return {
            "code_url": f"weixin://wxpay/test_{order_no}",
            "test_mode": True,
        }

    nonce_str = uuid.uuid4().hex[:32]
    params = {
        "appid": config.WX_APPID,
        "mch_id": config.WX_MCH_ID,
        "nonce_str": nonce_str,
        "body": description,
        "out_trade_no": order_no,
        "total_fee": amount_fen,
        "spbill_create_ip": "127.0.0.1",
        "notify_url": config.WX_PAY_NOTIFY_URL,
        "trade_type": "NATIVE",
    }
    params["sign"] = _make_sign(params, config.WX_MCH_KEY)

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "https://api.mch.weixin.qq.com/pay/unifiedorder",
                content=_dict_to_xml(params),
                headers={"Content-Type": "application/xml"},
                timeout=15,
            )
        result = _xml_to_dict(resp.text)

        if result.get("return_code") != "SUCCESS" or result.get("result_code") != "SUCCESS":
            logger.error(f"[支付-Native] 统一下单失败: {result}")
            return None

        return {
            "code_url": result["code_url"],
            "test_mode": False,
        }

    except Exception as e:
        logger.error(f"[支付-Native] 异常: {e}")
        return None


def verify_notify(xml_str: str) -> Optional[dict]:
    """验证微信支付回调通知"""
    try:
        data = _xml_to_dict(xml_str)
        sign = data.pop("sign", "")
        if not config.WX_MCH_KEY:
            return data
        calc_sign = _make_sign(data, config.WX_MCH_KEY)
        if calc_sign != sign:
            logger.error("[支付] 回调签名验证失败")
            return None
        return data
    except Exception as e:
        logger.error(f"[支付] 解析回调失败: {e}")
        return None
