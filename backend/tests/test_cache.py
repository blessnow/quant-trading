import pytest


@pytest.mark.asyncio
async def test_memory_cache_set_get():
    from cache import MemoryCache

    cache = MemoryCache()
    await cache.set("key1", "value1", ex=60)
    result = await cache.get("key1")
    assert result == "value1"


@pytest.mark.asyncio
async def test_memory_cache_miss():
    from cache import MemoryCache

    cache = MemoryCache()
    result = await cache.get("nonexistent")
    assert result is None


@pytest.mark.asyncio
async def test_memory_cache_delete():
    from cache import MemoryCache

    cache = MemoryCache()
    await cache.set("key1", "value1", ex=60)
    await cache.delete("key1")
    result = await cache.get("key1")
    assert result is None


@pytest.mark.asyncio
async def test_cache_key_generation():
    from cache import cache_key

    assert cache_key("stock", "600519") == "stock:600519"
    assert cache_key("a", "b", "c") == "a:b:c"
