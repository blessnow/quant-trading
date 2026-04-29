"""BACKEND_PRIVATE_ONLY 时：经公网域名进来的请求仅放行白名单路径（其余 404）。

内网 Host（*.railway.internal）、私网 TCP 对端、本地回环一律放行。须配合 Railway 关闭后端公网
或作为应用层加固；微信/开放平台回调路径需保留公网可达。"""
from __future__ import annotations

import ipaddress

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

import config


def _peer_is_private_rfc1918(peer: str | None) -> bool:
    """Railway 前端经私网直连后端时，对端为容器私网 IP；不依赖 X-Forwarded-For（可伪造）。"""
    if not peer:
        return False
    try:
        ip = ipaddress.ip_address(peer.strip())
    except ValueError:
        return False
    return bool(ip.is_private or ip.is_loopback or ip.is_link_local)


def _host_is_internal(host_header: str) -> bool:
    h = (host_header or "").split(":")[0].strip().lower()
    if not h:
        return False
    if ".railway.internal" in h:
        return True
    if h in ("127.0.0.1", "localhost", "::1"):
        return True
    return False


class PrivateBackendAccessMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        if not config.BACKEND_PRIVATE_ONLY:
            return await call_next(request)

        host = request.headers.get("host") or ""
        if _host_is_internal(host):
            return await call_next(request)

        client_host = request.client.host if request.client else None
        if client_host and _peer_is_private_rfc1918(client_host):
            return await call_next(request)

        path = request.url.path.rstrip("/") or "/"
        allowed = {p.rstrip("/") or "/" for p in config.BACKEND_PUBLIC_ALLOWED_PATHS}
        if path in allowed:
            return await call_next(request)

        return JSONResponse({"detail": "Not Found"}, status_code=404)
