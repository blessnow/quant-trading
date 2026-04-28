"""API 限流中间件"""
import os
from fastapi import FastAPI, Request, HTTPException
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

RATE_LIMIT_ENABLED = os.environ.get("RATE_LIMIT_ENABLED", "true").lower() == "true"
RATE_LIMIT_DEFAULT = os.environ.get("RATE_LIMIT_DEFAULT", "100/minute")
RATE_LIMIT_CHAT = os.environ.get("RATE_LIMIT_CHAT", "20/minute")
RATE_LIMIT_LOGIN = os.environ.get("RATE_LIMIT_LOGIN", "10/minute")


def get_rate_limit_key(request: Request) -> str:
    """获取限流键（优先使用用户ID，其次IP）"""
    user_id = None
    
    token = request.cookies.get("token") or request.headers.get("Authorization", "").replace("Bearer ", "")
    if token:
        try:
            import jwt
            from config import JWT_SECRET
            payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
            user_id = payload.get("user_id")
        except Exception:
            pass
    
    if user_id:
        return f"user:{user_id}"
    
    return f"ip:{get_remote_address(request)}"


limiter = Limiter(
    key_func=get_rate_limit_key,
    default_limits=[RATE_LIMIT_DEFAULT] if RATE_LIMIT_ENABLED else [],
    enabled=RATE_LIMIT_ENABLED,
)


def setup_rate_limit(app: FastAPI):
    """配置限流中间件"""
    if not RATE_LIMIT_ENABLED:
        return
    
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.add_middleware(SlowAPIMiddleware)
