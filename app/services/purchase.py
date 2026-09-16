"""ERP 采购域服务：采购申请/订单状态机与业务规则。"""
from __future__ import annotations

import uuid

from fastapi import HTTPException, Request, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import internal_write_allowed
from app.models.purchase import PurchaseOrder, PurchaseRequest
from app.repositories import purchase as repo
from app.schemas.purchase import PurchaseOrderCreate, PurchaseRequestCreate
from app.services.audit import record_audit

# 采购申请合法状态迁移表
_REQUEST_TRANSITIONS: dict[str, set[str]] = {
    "draft": {"submitted", "cancelled"},
    "submitted": {"approved", "rejected", "cancelled"},
    "approved": set(),
    "rejected": set(),
    "cancelled": set(),
}

# 采购订单合法状态迁移表
_ORDER_TRANSITIONS: dict[str, set[str]] = {
    "issued": {"received", "cancelled"},
    "received": {"closed", "cancelled"},
    "closed": set(),
    "cancelled": set(),
}

_ACTION_TO_REQUEST_STATUS = {
    "submit": "submitted", "approve": "approved", "reject": "rejected", "cancel": "cancelled",
}
_ACTION_TO_ORDER_STATUS = {
    "receive": "received", "close": "closed", "cancel": "cancelled",
}


def _request_to_dict(r: PurchaseRequest) -> dict:
    return {
        "id": r.id, "code": r.code, "requester_id": r.requester_id,
        "department_id": r.department_id, "title": r.title, "reason": r.reason,
        "amount": r.amount, "status": r.status,
        "created_at": r.created_at.isoformat() if r.created_at else "",
        "updated_at": r.updated_at.isoformat() if r.updated_at else "",
    }


def _order_to_dict(o: PurchaseOrder) -> dict:
    return {
        "id": o.id, "po_number": o.po_number, "pr_id": o.pr_id, "supplier": o.supplier,
        "amount": o.amount, "status": o.status,
        "order_date": o.order_date.isoformat() if o.order_date else "",
        "created_at": o.created_at.isoformat() if o.created_at else "",
        "updated_at": o.updated_at.isoformat() if o.updated_at else "",
    }


class PurchaseRequestService:
    @staticmethod
    async def list_requests(session: AsyncSession, limit: int, offset: int,
                            status_filter: str | None, keyword: str | None) -> dict:
        rows = await repo.list_requests(session, limit, offset, status_filter, keyword)
        total = await repo.count_requests(session, status_filter, keyword)
        return {"total": total, "items": [_request_to_dict(r) for r in rows]}

    @staticmethod
    async def get_request(session: AsyncSession, pr_id: str) -> dict:
        r = await repo.get_request(session, pr_id)
        if not r:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "采购申请不存在")
        return _request_to_dict(r)

    @staticmethod
    async def create_request(session: AsyncSession, payload: PurchaseRequestCreate,
                             request: Request) -> dict:
        if not internal_write_allowed(request):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "内部写入令牌无效")
        if payload.amount < 0:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "采购金额不能为负")
        if await repo.get_request_by_code(session, payload.code):
            raise HTTPException(status.HTTP_409_CONFLICT, "采购申请编号已存在")
        pr = PurchaseRequest(
            id=str(uuid.uuid4()), code=payload.code, requester_id=payload.requester_id,
            department_id=payload.department_id, title=payload.title,
            reason=payload.reason, amount=payload.amount, status="draft",
        )
        try:
            pr = await repo.create_request(session, pr)
        except IntegrityError as exc:
            raise HTTPException(status.HTTP_409_CONFLICT, "采购申请编号已存在") from exc
        await record_audit(session, "purchase_request.created", "internal",
                           f"pr_id={pr.id} code={payload.code}", request)
        return _request_to_dict(pr)

    @staticmethod
    async def transition(session: AsyncSession, pr_id: str, action: str,
                         request: Request) -> dict:
        if not internal_write_allowed(request):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "内部写入令牌无效")
        pr = await repo.get_request(session, pr_id)
        if not pr:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "采购申请不存在")
        target = _ACTION_TO_REQUEST_STATUS[action]
        if target not in _REQUEST_TRANSITIONS.get(pr.status, set()):
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                f"采购申请当前状态 {pr.status} 不允许执行 {action}",
            )
        pr.status = target
        pr = await repo.update_request(session, pr)
        await record_audit(session, "purchase_request.status_changed", "internal",
                           f"pr_id={pr_id} action={action}", request)
        return _request_to_dict(pr)


class PurchaseOrderService:
    @staticmethod
    async def list_orders(session: AsyncSession, limit: int, offset: int,
                          status_filter: str | None, keyword: str | None) -> dict:
        rows = await repo.list_orders(session, limit, offset, status_filter, keyword)
        total = await repo.count_orders(session, status_filter, keyword)
        return {"total": total, "items": [_order_to_dict(o) for o in rows]}

    @staticmethod
    async def get_order(session: AsyncSession, po_id: str) -> dict:
        o = await repo.get_order(session, po_id)
        if not o:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "采购订单不存在")
        return _order_to_dict(o)

    @staticmethod
    async def create_order(session: AsyncSession, payload: PurchaseOrderCreate,
                           request: Request) -> dict:
        if not internal_write_allowed(request):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "内部写入令牌无效")
        if payload.amount < 0:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "订单金额不能为负")
        pr = await repo.get_request(session, payload.pr_id)
        if not pr:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "关联采购申请不存在")
        # 业务规则：仅审批通过的申请可生成采购订单
        if pr.status != "approved":
            raise HTTPException(status.HTTP_409_CONFLICT,
                                f"采购申请状态为 {pr.status}，须审批通过后方可下单")
        po_number = f"PO-{uuid.uuid4().hex[:10].upper()}"
        po = PurchaseOrder(
            id=str(uuid.uuid4()), po_number=po_number, pr_id=pr.id,
            supplier=payload.supplier, amount=payload.amount,
            order_date=payload.order_date, status="issued",
        )
        try:
            po = await repo.create_order(session, po)
        except IntegrityError as exc:
            raise HTTPException(status.HTTP_409_CONFLICT, "采购订单编号已存在") from exc
        await record_audit(session, "purchase_order.created", "internal",
                           f"po_id={po.id} pr_id={pr.id}", request)
        return _order_to_dict(po)

    @staticmethod
    async def transition(session: AsyncSession, po_id: str, action: str,
                         request: Request) -> dict:
        if not internal_write_allowed(request):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "内部写入令牌无效")
        po = await repo.get_order(session, po_id)
        if not po:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "采购订单不存在")
        target = _ACTION_TO_ORDER_STATUS[action]
        if target not in _ORDER_TRANSITIONS.get(po.status, set()):
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                f"采购订单当前状态 {po.status} 不允许执行 {action}",
            )
        po.status = target
        po = await repo.update_order(session, po)
        await record_audit(session, "purchase_order.status_changed", "internal",
                           f"po_id={po_id} action={action}", request)
        return _order_to_dict(po)
