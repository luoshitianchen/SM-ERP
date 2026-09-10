"""健康检查与安全响应头测试。"""
from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_health_endpoint(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert "service" in data and "version" in data


@pytest.mark.asyncio
async def test_readyz_endpoint(client):
    resp = await client.get("/readyz")
    assert resp.status_code == 200
    data = resp.json()
    assert "status" in data and "checks" in data


@pytest.mark.asyncio
async def test_security_headers(client):
    resp = await client.get("/health")
    assert resp.headers.get("X-Content-Type-Options") == "nosniff"
    assert resp.headers.get("X-Frame-Options") == "DENY"
    assert "Content-Security-Policy" in resp.headers
    assert "X-Request-Id" in resp.headers
