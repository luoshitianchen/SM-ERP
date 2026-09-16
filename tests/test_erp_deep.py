"""ERP 业务深化测试：采购申请/订单状态机、库存出入库、员工入职与部门层级。"""
from __future__ import annotations

H = {"X-Internal-Token": "test-internal-key-12345"}


# ═══════════════════════════════════════════════════════════
# 采购申请
# ═══════════════════════════════════════════════════════════
class TestPurchaseRequest:
    async def test_create_request_success(self, client):
        resp = await client.post("/api/purchase/requests", json={
            "code": "PR-2026-001", "requester_id": "emp-01", "department_id": "engineering",
            "title": "采购笔记本", "reason": "新员工入职", "amount": 12000.5,
        }, headers=H)
        assert resp.status_code == 201
        data = resp.json()
        assert data["code"] == "PR-2026-001"
        assert data["status"] == "draft"

    async def test_create_request_requires_token(self, client):
        resp = await client.post("/api/purchase/requests", json={
            "code": "PR-NOTOKEN", "department_id": "engineering", "title": "x", "amount": 1,
        })
        assert resp.status_code in (401, 403)

    async def test_create_request_duplicate_code(self, client):
        await client.post("/api/purchase/requests", json={
            "code": "PR-DUP", "department_id": "engineering", "title": "重复", "amount": 100,
        }, headers=H)
        resp = await client.post("/api/purchase/requests", json={
            "code": "PR-DUP", "department_id": "engineering", "title": "重复2", "amount": 100,
        }, headers=H)
        assert resp.status_code == 409

    async def test_create_request_negative_amount(self, client):
        resp = await client.post("/api/purchase/requests", json={
            "code": "PR-NEG", "department_id": "engineering", "title": "负金额", "amount": -10,
        }, headers=H)
        assert resp.status_code in (400, 422)

    async def test_request_status_machine_happy_path(self, client):
        create = await client.post("/api/purchase/requests", json={
            "code": "PR-SM", "department_id": "engineering", "title": "状态机", "amount": 1,
        }, headers=H)
        pr_id = create.json()["id"]
        r = await client.patch(f"/api/purchase/requests/{pr_id}/transition",
                               json={"action": "submit"}, headers=H)
        assert r.json()["status"] == "submitted"
        r = await client.patch(f"/api/purchase/requests/{pr_id}/transition",
                               json={"action": "approve"}, headers=H)
        assert r.json()["status"] == "approved"

    async def test_request_invalid_transition(self, client):
        create = await client.post("/api/purchase/requests", json={
            "code": "PR-BAD", "department_id": "engineering", "title": "非法迁移", "amount": 1,
        }, headers=H)
        pr_id = create.json()["id"]
        # draft 不可直接 approve
        r = await client.patch(f"/api/purchase/requests/{pr_id}/transition",
                               json={"action": "approve"}, headers=H)
        assert r.status_code == 409

    async def test_request_reject_and_list_filter(self, client):
        create = await client.post("/api/purchase/requests", json={
            "code": "PR-REJ", "department_id": "engineering", "title": "驳回", "amount": 1,
        }, headers=H)
        pr_id = create.json()["id"]
        await client.patch(f"/api/purchase/requests/{pr_id}/transition",
                           json={"action": "submit"}, headers=H)
        r = await client.patch(f"/api/purchase/requests/{pr_id}/transition",
                               json={"action": "reject"}, headers=H)
        assert r.json()["status"] == "rejected"
        lst = await client.get("/api/purchase/requests?status=rejected&keyword=驳回", headers=H)
        assert lst.status_code == 200
        assert lst.json()["total"] >= 1

    async def test_get_request_not_found(self, client):
        resp = await client.get("/api/purchase/requests/nope", headers=H)
        assert resp.status_code == 404


# ═══════════════════════════════════════════════════════════
# 采购订单
# ═══════════════════════════════════════════════════════════
class TestPurchaseOrder:
    async def _approved_pr(self, client, code="PR-PO"):
        create = await client.post("/api/purchase/requests", json={
            "code": code, "department_id": "engineering", "title": "订单申请", "amount": 500,
        }, headers=H)
        pr_id = create.json()["id"]
        await client.patch(f"/api/purchase/requests/{pr_id}/transition",
                           json={"action": "submit"}, headers=H)
        await client.patch(f"/api/purchase/requests/{pr_id}/transition",
                           json={"action": "approve"}, headers=H)
        return pr_id

    async def test_order_create_only_after_approval(self, client):
        create = await client.post("/api/purchase/requests", json={
            "code": "PR-PO-DRAFT", "department_id": "engineering", "title": "草稿", "amount": 500,
        }, headers=H)
        pr_id = create.json()["id"]
        resp = await client.post("/api/purchase/orders", json={
            "pr_id": pr_id, "supplier": "供应商A", "amount": 500, "order_date": "2026-09-16",
        }, headers=H)
        assert resp.status_code == 409

    async def test_order_create_and_transition(self, client):
        pr_id = await self._approved_pr(client, "PR-PO-OK")
        resp = await client.post("/api/purchase/orders", json={
            "pr_id": pr_id, "supplier": "供应商B", "amount": 500, "order_date": "2026-09-16",
        }, headers=H)
        assert resp.status_code == 201
        po_id = resp.json()["id"]
        assert resp.json()["status"] == "issued"
        r = await client.patch(f"/api/purchase/orders/{po_id}/transition",
                              json={"action": "receive"}, headers=H)
        assert r.json()["status"] == "received"
        r = await client.patch(f"/api/purchase/orders/{po_id}/transition",
                              json={"action": "close"}, headers=H)
        assert r.json()["status"] == "closed"

    async def test_order_invalid_transition(self, client):
        pr_id = await self._approved_pr(client, "PR-PO-BAD")
        po = (await client.post("/api/purchase/orders", json={
            "pr_id": pr_id, "supplier": "供应商C", "amount": 100, "order_date": "2026-09-16",
        }, headers=H)).json()
        # issued 不可直接 close
        r = await client.patch(f"/api/purchase/orders/{po['id']}/transition",
                              json={"action": "close"}, headers=H)
        assert r.status_code == 409

    async def test_order_list_pagination(self, client):
        resp = await client.get("/api/purchase/orders?limit=5&offset=0", headers=H)
        assert resp.status_code == 200
        assert "total" in resp.json() and "items" in resp.json()


# ═══════════════════════════════════════════════════════════
# 库存
# ═══════════════════════════════════════════════════════════
class TestInventory:
    async def test_create_stock_item(self, client):
        resp = await client.post("/api/inventory/items", json={
            "sku": "SKU-KB-001", "name": "机械键盘", "unit": "个",
            "quantity": 100, "safety_stock": 20, "unit_price": 299.5,
        }, headers=H)
        assert resp.status_code == 201
        assert resp.json()["sku"] == "SKU-KB-001"
        assert resp.json()["low_stock"] is False

    async def test_create_stock_duplicate_sku(self, client):
        await client.post("/api/inventory/items", json={
            "sku": "SKU-DUP", "name": "重复",
        }, headers=H)
        resp = await client.post("/api/inventory/items", json={
            "sku": "SKU-DUP", "name": "重复2",
        }, headers=H)
        assert resp.status_code == 409

    async def test_inbound_updates_quantity(self, client):
        item = (await client.post("/api/inventory/items", json={
            "sku": "SKU-IN", "name": "入库测试", "quantity": 10, "safety_stock": 5,
        }, headers=H)).json()
        resp = await client.post("/api/inventory/transactions", json={
            "stock_item_id": item["id"], "direction": "in", "change_qty": 5,
        }, headers=H)
        assert resp.status_code == 201
        assert resp.json()["quantity"] == 15

    async def test_outbound_insufficient_rejected(self, client):
        item = (await client.post("/api/inventory/items", json={
            "sku": "SKU-OUT", "name": "出库测试", "quantity": 2, "safety_stock": 0,
        }, headers=H)).json()
        resp = await client.post("/api/inventory/transactions", json={
            "stock_item_id": item["id"], "direction": "out", "change_qty": 99,
        }, headers=H)
        assert resp.status_code == 409

    async def test_outbound_triggers_low_stock(self, client):
        item = (await client.post("/api/inventory/items", json={
            "sku": "SKU-LOW", "name": "低库存", "quantity": 10, "safety_stock": 8,
        }, headers=H)).json()
        resp = await client.post("/api/inventory/transactions", json={
            "stock_item_id": item["id"], "direction": "out", "change_qty": 5,
        }, headers=H)
        assert resp.status_code == 201
        assert resp.json()["quantity"] == 5
        assert resp.json()["low_stock"] is True

    async def test_list_items_and_transactions(self, client):
        lst = await client.get("/api/inventory/items?keyword=低库存", headers=H)
        assert lst.status_code == 200
        tx = await client.get("/api/inventory/transactions?direction=out", headers=H)
        assert tx.status_code == 200
        assert tx.json()["total"] >= 1


# ═══════════════════════════════════════════════════════════
# 员工/部门增强规则
# ═══════════════════════════════════════════════════════════
class TestEmployeeEnhanced:
    async def test_hire_date_in_future_rejected(self, client):
        resp = await client.post("/api/employees", json={
            "username": "futurehire", "password": "Secret123", "name": "未来入职",
            "department": "engineering", "hire_date": "2099-01-01",
        }, headers=H)
        assert resp.status_code == 400

    async def test_hire_date_accepted(self, client):
        resp = await client.post("/api/employees", json={
            "username": "pasthire", "password": "Secret123", "name": "正常入职",
            "department": "engineering", "hire_date": "2024-01-01",
        }, headers=H)
        assert resp.status_code == 201

    async def test_department_parent_not_found(self, client):
        resp = await client.post("/api/departments", json={
            "id": "ghost", "name": "幽灵部门", "parent_id": "no_such_parent",
        }, headers=H)
        assert resp.status_code == 422

    async def test_department_self_reference_rejected(self, client):
        resp = await client.post("/api/departments", json={
            "id": "selfdept", "name": "自引用", "parent_id": "selfdept",
        }, headers=H)
        assert resp.status_code == 400
