"""测试配置：内存 SQLite + 异步客户端。"""
from __future__ import annotations

import os

# 测试环境必须在导入 app 前设置
os.environ["SM_ENV"] = "test"
os.environ["SM_DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ["SM_INTERNAL_API_KEY"] = "test-internal-key-12345"
os.environ["SM_JWT_SECRET"] = "test-jwt-secret-for-testing-only-0001"
os.environ["SM_SM4_KEY_HEX"] = "0123456789abcdef0123456789abcdef"

import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.core.database import init_db  # noqa: E402
from app.main import app  # noqa: E402


@pytest_asyncio.fixture
async def client():
    await init_db()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac
