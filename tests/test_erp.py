"""ERP 身份域端点测试（v2.5.0 业务逻辑迁移验收）。"""
from __future__ import annotations

import pytest

H = {"X-Internal-Token": "test-internal-key-12345"}


@pytest.mark.asyncio
async def test_list_seeded_departments(client):
    resp = await client.get("/api/departments", headers=H)
    assert resp.status_code == 200
    ids = {d["id"] for d in resp.json()}
    assert {"engineering", "finance"} <= ids


@pytest.mark.asyncio
async def test_create_department(client):
    resp = await client.post("/api/departments", json={"id": "sales", "name": "销售部"}, headers=H)
    assert resp.status_code == 201
    assert resp.json()["id"] == "sales"


@pytest.mark.asyncio
async def test_create_employee(client):
    resp = await client.post(
        "/api/employees",
        json={"username": "zhangsan", "password": "Secret123", "name": "张三", "department": "engineering"},
        headers=H,
    )
    assert resp.status_code == 201
    assert resp.json()["username"] == "zhangsan"


@pytest.mark.asyncio
async def test_create_employee_bad_department(client):
    resp = await client.post(
        "/api/employees",
        json={"username": "lisi", "password": "Secret123", "name": "李四", "department": "no_such_dept"},
        headers=H,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_list_employees_contains_admin(client):
    await client.post(
        "/api/employees",
        json={"username": "wangwu", "password": "Secret123", "name": "王五", "department": "finance"},
        headers=H,
    )
    resp = await client.get("/api/employees", headers=H)
    assert resp.status_code == 200
    usernames = {e["username"] for e in resp.json()}
    assert "admin" in usernames and "wangwu" in usernames


@pytest.mark.asyncio
async def test_update_employee_status(client):
    create = await client.post(
        "/api/employees",
        json={"username": "zhaoliu", "password": "Secret123", "name": "赵六", "department": "finance"},
        headers=H,
    )
    emp_id = create.json()["id"]
    resp = await client.patch(f"/api/employees/{emp_id}/status", json={"active": False}, headers=H)
    assert resp.status_code == 200
    assert resp.json()["active"] is False


@pytest.mark.asyncio
async def test_update_nonexistent_employee(client):
    resp = await client.patch("/api/employees/nope/status", json={"active": False}, headers=H)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_employee_requires_token(client):
    resp = await client.post(
        "/api/employees",
        json={"username": "intruder", "password": "Secret123", "name": "闯入者", "department": "engineering"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_dashboard(client):
    resp = await client.get("/api/dashboard", headers=H)
    assert resp.status_code == 200
    data = resp.json()
    assert data["departments"] >= 2
    assert data["employees"] >= 1
