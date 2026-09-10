"""安全控制测试。"""
from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_unauthenticated_rejected(client):
    """未认证请求被中间件拒绝（401）。"""
    resp = await client.post("/api/items", json={"name": "test"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_internal_token_success(client):
    """携带有效内部令牌可以创建业务项。"""
    resp = await client.post(
        "/api/items",
        json={"name": "安全测试", "owner": "测试部", "priority": "P2", "status": "active"},
        headers={"X-Internal-Token": "test-internal-key-12345"},
    )
    assert resp.status_code == 201
    assert resp.json()["name"] == "安全测试"


@pytest.mark.asyncio
async def test_invalid_token_rejected(client):
    """无效内部令牌被拒绝（401）。"""
    resp = await client.post(
        "/api/items", json={"name": "test"},
        headers={"X-Internal-Token": "wrong"},
    )
    assert resp.status_code == 401
