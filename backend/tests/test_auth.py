import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["BCRYPT_ROUNDS"] = "4"

import pytest


@pytest.mark.asyncio
async def test_password_hash_and_verify():
    from auth import hash_password, verify_password

    hashed = hash_password("test123")
    assert hashed != "test123"
    assert verify_password("test123", hashed) is True
    assert verify_password("wrong", hashed) is False


@pytest.mark.asyncio
async def test_hash_password_different_salts():
    from auth import hash_password

    h1 = hash_password("same_password")
    h2 = hash_password("same_password")
    assert h1 != h2
