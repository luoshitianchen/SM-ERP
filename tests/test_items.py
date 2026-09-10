"""业务项 CRUD 测试。"""
from __future__ import annotations

import pytest

H = {"X-Internal-Token": "test-internal-key-12345"}


@pytest.mark.asyncio
async def test_create_item(client):
    resp = await client.post("/api/items", json={"name": "测试项", "owner": "测试部"}, headers=H)
    assert resp.status_code == 201
    assert resp.json()["name"] == "测试项"


@pytest.mark.asyncio
async def test_update_status(client):
    create = await client.post("/api/items", json={"name": "状态测试"}, headers=H)
    item_id = create.json()["id"]
    resp = await client.patch(f"/api/items/{item_id}/status", json={"status": "closed"}, headers=H)
    assert resp.status_code == 200
    assert resp.json()["status"] == "closed"


@pytest.mark.asyncio
async def test_update_nonexistent(client):
    resp = await client.patch("/api/items/nope/status", json={"status": "closed"}, headers=H)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_overview(client):
    await client.post("/api/items", json={"name": "概览项"}, headers=H)
    resp = await client.get("/api/overview")
    assert resp.status_code == 200
    assert resp.json()["total"] >= 1
