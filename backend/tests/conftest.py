import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["BCRYPT_ROUNDS"] = "4"
os.environ["STORAGE_DIR"] = "/tmp/quant_test_storage"

import pytest
import asyncio


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


_db_initialized = False


@pytest.fixture(autouse=True)
async def setup_test_db():
    global _db_initialized
    if not _db_initialized:
        from database import init_db
        await init_db()
        _db_initialized = True
    yield
