"""Redis 缓存层"""
import json
import os
from datetime import timedelta
from typing import Optional, Any
import redis.asyncio as redis
from loguru import logger

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
REDIS_ENABLED = os.environ.get("REDIS_ENABLED", "false").lower() == "true"

_redis_client: Optional[redis.Redis] = None


async def init_redis():
    """初始化 Redis 连接"""
    global _redis_client
    if not REDIS_ENABLED:
        logger.info("[缓存] Redis 未启用，使用内存缓存")
        return
    
    try:
        _redis_client = redis.from_url(REDIS_URL, decode_responses=True)
        await _redis_client.ping()
        logger.info(f"[缓存] Redis 连接成功: {REDIS_URL}")
    except Exception as e:
        logger.warning(f"[缓存] Redis 连接失败，使用内存缓存: {e}")
        _redis_client = None


async def close_redis():
    """关闭 Redis 连接"""
    global _redis_client
    if _redis_client:
        await _redis_client.close()
        _redis_client = None


class MemoryCache:
    """内存缓存（Redis 不可用时的降级方案）"""
    def __init__(self):
        self._cache: dict[str, tuple[Any, float]] = {}
    
    def _is_expired(self, key: str) -> bool:
        """检查是否过期"""
        import time
        if key not in self._cache:
            return True
        _, expire_at = self._cache[key]
        return expire_at > 0 and time.time() > expire_at
    
    async def get(self, key: str) -> Optional[str]:
        if self._is_expired(key):
            self._cache.pop(key, None)
            return None
        return self._cache[key][0]
    
    async def set(self, key: str, value: str, ex: int = 0):
        import time
        expire_at = time.time() + ex if ex > 0 else 0
        self._cache[key] = (value, expire_at)
    
    async def delete(self, key: str):
        self._cache.pop(key, None)
    
    async def exists(self, key: str) -> bool:
        return not self._is_expired(key)


_memory_cache = MemoryCache()


async def cache_get(key: str) -> Optional[str]:
    """获取缓存"""
    if _redis_client:
        try:
            return await _redis_client.get(key)
        except Exception as e:
            logger.warning(f"[缓存] Redis 读取失败: {e}")
    return await _memory_cache.get(key)


async def cache_set(key: str, value: Any, ttl: int = 300):
    """设置缓存"""
    if isinstance(value, (dict, list)):
        value = json.dumps(value, ensure_ascii=False)
    
    if _redis_client:
        try:
            await _redis_client.set(key, value, ex=ttl)
            return
        except Exception as e:
            logger.warning(f"[缓存] Redis 写入失败: {e}")
    
    await _memory_cache.set(key, value, ttl)


async def cache_delete(key: str):
    """删除缓存"""
    if _redis_client:
        try:
            await _redis_client.delete(key)
        except Exception as e:
            logger.warning(f"[缓存] Redis 删除失败: {e}")
    await _memory_cache.delete(key)


async def cache_get_json(key: str) -> Optional[Any]:
    """获取 JSON 缓存"""
    value = await cache_get(key)
    if value:
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return None
    return None


def cache_key(*parts: str) -> str:
    """生成缓存键"""
    return ":".join(str(p) for p in parts)


CACHE_TTL = {
    "stock_price": 30,
    "stock_history": 300,
    "zt_pool": 60,
    "industry_board": 300,
    "market_emotion": 60,
    "stock_fundamentals": 3600,
    "pb_ratio": 300,
    "commodity_prices": 60,
    "usd_cny_rate": 3600,
}
