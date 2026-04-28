import pytest


@pytest.mark.asyncio
async def test_get_db_returns_connection():
    from database import get_db

    db = await get_db()
    assert db is not None
    await db.close()


@pytest.mark.asyncio
async def test_db_connection_basic_query():
    from database import get_db

    db = await get_db()
    try:
        async with db.execute("SELECT 1") as cur:
            row = await cur.fetchone()
        assert row[0] == 1
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_strategies_table_exists():
    from database import get_db

    db = await get_db()
    try:
        async with db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='strategies'") as cur:
            row = await cur.fetchone()
        assert row is not None
    finally:
        await db.close()
