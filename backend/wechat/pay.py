"""微信支付工具（APIv3 JSON + RSA-SHA256；无商户号时 mock）"""
import base64
import json
import time
import uuid
from typing import Any, Optional

import httpx
from cryptography import x509
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from loguru import logger

import config

_WX_API_BASE = "https://api.mch.weixin.qq.com"
_PLATFORM_CERTS: dict[str, bytes] = {}  # serial_no -> PEM bytes
_PLATFORM_CERTS_FETCHED_AT: float = 0.0
_CERT_CACHE_TTL = 3600 * 12


def _v3_ready() -> bool:
    return bool(
        config.WX_MCH_ID
        and config.WX_MCH_SERIAL_NO
        and config.WX_API_V3_KEY
        and len(config.WX_API_V3_KEY.encode("utf-8")) == 32
        and config.WX_MCH_PRIVATE_KEY_PATH
    )


def _load_mch_private_key():
    path = config.WX_MCH_PRIVATE_KEY_PATH
    with open(path, "rb") as f:
        return serialization.load_pem_private_key(f.read(), password=None)


def _sign_v3(method: str, url_path: str, timestamp: str, nonce_str: str, body: str, private_key) -> str:
    message = f"{method}\n{url_path}\n{timestamp}\n{nonce_str}\n{body}\n"
    sig = private_key.sign(message.encode("utf-8"), padding.PKCS1v15(), hashes.SHA256())
    return base64.b64encode(sig).decode("ascii")


def _authorization_v3(method: str, url_path: str, body: str, private_key) -> str:
    ts = str(int(time.time()))
    nonce = uuid.uuid4().hex
    sig_b64 = _sign_v3(method, url_path, ts, nonce, body, private_key)
    token = (
        f'mchid="{config.WX_MCH_ID}",'
        f'nonce_str="{nonce}",'
        f'timestamp="{ts}",'
        f'serial_no="{config.WX_MCH_SERIAL_NO}",'
        f'signature="{sig_b64}"'
    )
    return f"WECHATPAY2-SHA256-RSA2048 {token}"


def _decrypt_certificate(aes_key: str, enc: dict) -> str:
    nonce = enc["nonce"].encode("utf-8")
    ad = enc.get("associated_data", "").encode("utf-8")
    ct = base64.b64decode(enc["ciphertext"])
    key = aes_key.encode("utf-8")
    if len(key) != 32:
        raise ValueError("WX_API_V3_KEY must be 32 bytes")
    aesgcm = AESGCM(key)
    plain = aesgcm.decrypt(nonce, ct, ad)
    return plain.decode("utf-8")


def _decrypt_notify_resource(aes_key: str, resource: dict) -> dict:
    nonce = resource["nonce"].encode("utf-8")
    ad = (resource.get("associated_data") or "").encode("utf-8")
    ct = base64.b64decode(resource["ciphertext"])
    key = aes_key.encode("utf-8")
    aesgcm = AESGCM(key)
    plain = aesgcm.decrypt(nonce, ct, ad)
    return json.loads(plain.decode("utf-8"))


async def _refresh_platform_certificates(force: bool = False) -> None:
    global _PLATFORM_CERTS, _PLATFORM_CERTS_FETCHED_AT
    now = time.time()
    if not force and _PLATFORM_CERTS and (now - _PLATFORM_CERTS_FETCHED_AT) < _CERT_CACHE_TTL:
        return
    if not _v3_ready():
        return

    private_key = _load_mch_private_key()
    path = "/v3/certificates"
    body = ""
    auth = _authorization_v3("GET", path, body, private_key)
    async with httpx.AsyncClient() as client:
        r = await client.get(
            f"{_WX_API_BASE}{path}",
            headers={"Authorization": auth, "Accept": "application/json"},
            timeout=20,
        )
    if r.status_code != 200:
        logger.error(f"[支付] 拉取平台证书失败: {r.status_code} {r.text}")
        return

    data = r.json().get("data") or []
    new_certs: dict[str, bytes] = {}
    for item in data:
        serial = item.get("serial_no")
        enc = item.get("encrypt_certificate")
        if not serial or not enc:
            continue
        try:
            pem = _decrypt_certificate(config.WX_API_V3_KEY, enc)
            new_certs[serial] = pem.encode("utf-8")
        except Exception as e:
            logger.error(f"[支付] 解密平台证书失败 serial={serial}: {e}")

    if new_certs:
        _PLATFORM_CERTS = new_certs
        _PLATFORM_CERTS_FETCHED_AT = now


def _verify_wechatpay_signature(
    timestamp: str,
    nonce: str,
    body: str,
    signature_b64: str,
    serial: str,
) -> bool:
    pem = _PLATFORM_CERTS.get(serial)
    if not pem:
        return False
    try:
        cert = x509.load_pem_x509_certificate(pem, default_backend())
        pubkey = cert.public_key()
        message = f"{timestamp}\n{nonce}\n{body}\n".encode("utf-8")
        sig = base64.b64decode(signature_b64)
        pubkey.verify(sig, message, padding.PKCS1v15(), hashes.SHA256())
        return True
    except Exception as e:
        logger.error(f"[支付] 验签失败: {e}")
        return False


async def _v3_post(path: str, payload: dict) -> Optional[dict]:
    if not _v3_ready():
        logger.error("[支付] V3 配置不完整：需要 WX_MCH_ID、WX_MCH_SERIAL_NO、WX_API_V3_KEY(32位)、WX_MCH_PRIVATE_KEY_PATH")
        return None
    body_str = json.dumps(payload, ensure_ascii=False)
    private_key = _load_mch_private_key()
    auth = _authorization_v3("POST", path, body_str, private_key)
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{_WX_API_BASE}{path}",
                content=body_str.encode("utf-8"),
                headers={
                    "Authorization": auth,
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
                timeout=20,
            )
        if resp.status_code not in (200, 201):
            logger.error(f"[支付] V3 POST {path} 失败: {resp.status_code} {resp.text}")
            return None
        if not resp.text.strip():
            return {}
        return resp.json()
    except Exception as e:
        logger.error(f"[支付] V3 请求异常: {e}")
        return None


async def create_prepay_order(
    openid: str,
    order_no: str,
    amount_fen: int,
    description: str = "量化交易会员",
) -> Optional[dict]:
    """小程序 JSAPI：V3 下单并返回调起支付参数"""
    if not config.WX_MCH_ID:
        logger.info(f"[支付] 测试模式，模拟下单: {order_no} {amount_fen}分")
        return {
            "timeStamp": str(int(time.time())),
            "nonceStr": uuid.uuid4().hex[:32],
            "package": f"prepay_id=test_{order_no}",
            "signType": "RSA",
            "paySign": "test_sign",
        }

    if not _v3_ready():
        logger.error("[支付] 未配置完整 V3，无法创建预支付单")
        return None

    path = "/v3/pay/transactions/jsapi"
    payload: dict[str, Any] = {
        "appid": config.WX_APPID,
        "mchid": config.WX_MCH_ID,
        "description": description,
        "out_trade_no": order_no,
        "notify_url": config.WX_PAY_NOTIFY_URL,
        "amount": {"total": amount_fen, "currency": "CNY"},
        "payer": {"openid": openid},
    }
    result = await _v3_post(path, payload)
    if not result or "prepay_id" not in result:
        return None

    prepay_id = result["prepay_id"]
    ts = str(int(time.time()))
    nonce_str = uuid.uuid4().hex[:32]
    pkg = f"prepay_id={prepay_id}"
    private_key = _load_mch_private_key()
    pay_message = f"{config.WX_APPID}\n{ts}\n{nonce_str}\n{pkg}\n"
    pay_sig = base64.b64encode(
        private_key.sign(pay_message.encode("utf-8"), padding.PKCS1v15(), hashes.SHA256())
    ).decode("ascii")

    return {
        "appId": config.WX_APPID,
        "timeStamp": ts,
        "nonceStr": nonce_str,
        "package": pkg,
        "signType": "RSA",
        "paySign": pay_sig,
    }


async def create_native_order(
    order_no: str,
    amount_fen: int,
    description: str = "量化交易会员",
) -> Optional[dict]:
    """Native 扫码：V3 下单返回 code_url"""
    if not config.WX_MCH_ID:
        logger.info(f"[支付-Native] 测试模式，模拟下单: {order_no} {amount_fen}分")
        return {
            "code_url": f"weixin://wxpay/test_{order_no}",
            "test_mode": True,
        }

    if not _v3_ready():
        logger.error("[支付-Native] 未配置完整 V3，无法下单")
        return None

    path = "/v3/pay/transactions/native"
    payload = {
        "appid": config.WX_APPID,
        "mchid": config.WX_MCH_ID,
        "description": description,
        "out_trade_no": order_no,
        "notify_url": config.WX_PAY_NOTIFY_URL,
        "amount": {"total": amount_fen, "currency": "CNY"},
    }
    result = await _v3_post(path, payload)
    if not result or "code_url" not in result:
        return None
    return {"code_url": result["code_url"], "test_mode": False}


async def verify_notify(body: str, headers: dict[str, str]) -> Optional[dict]:
    """
    验证 V3 支付回调，返回与旧逻辑兼容的字段：out_trade_no, transaction_id, result_code。
    """
    if not config.WX_MCH_ID:
        return None

    if not _v3_ready():
        logger.error("[支付] 回调验签需要完整 V3 配置")
        return None

    ts = headers.get("wechatpay-timestamp") or headers.get("Wechatpay-Timestamp", "")
    nonce = headers.get("wechatpay-nonce") or headers.get("Wechatpay-Nonce", "")
    sig_b64 = headers.get("wechatpay-signature") or headers.get("Wechatpay-Signature", "")
    serial = headers.get("wechatpay-serial") or headers.get("Wechatpay-Serial", "")

    if not all([ts, nonce, sig_b64, serial, body]):
        logger.error("[支付] 回调缺少必要头或 body")
        return None

    await _refresh_platform_certificates()
    if serial not in _PLATFORM_CERTS:
        await _refresh_platform_certificates(force=True)

    if serial not in _PLATFORM_CERTS:
        logger.error(f"[支付] 无匹配平台证书 serial={serial}")
        return None

    if not _verify_wechatpay_signature(ts, nonce, body, sig_b64, serial):
        return None

    try:
        event = json.loads(body)
    except json.JSONDecodeError:
        logger.error("[支付] 回调 body 非 JSON")
        return None

    if event.get("event_type") != "TRANSACTION.SUCCESS":
        logger.warning(f"[支付] 非支付成功事件: {event.get('event_type')}")
        return None

    resource = event.get("resource") or {}
    if resource.get("algorithm") != "AEAD_AES_256_GCM":
        logger.error("[支付] 不支持的解密算法")
        return None

    try:
        plain = _decrypt_notify_resource(config.WX_API_V3_KEY, resource)
    except Exception as e:
        logger.error(f"[支付] 解密回调 resource 失败: {e}")
        return None

    trade_state = plain.get("trade_state")
    if trade_state != "SUCCESS":
        return None

    return {
        "out_trade_no": plain.get("out_trade_no"),
        "transaction_id": plain.get("transaction_id"),
        "result_code": "SUCCESS",
    }
