"""ERP 采购域路由：采购申请与采购订单。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.schemas.purchase import (
    OrderStatusUpdate,
    PurchaseOrderCreate,
    PurchaseRequestCreate,
    RequestStatusUpdate,
)
from app.services.purchase import PurchaseOrderService, PurchaseRequestService

router = APIRouter(prefix="/api/purchase", tags=["erp-purchase"])


@router.get("/requests")
async def list_requests(
    request: Request,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    status_filter: str | None = Query(default=None, alias="status"),
    keyword: str | None = Query(default=None),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await PurchaseRequestService.list_requests(
        session, limit, offset, status_filter, keyword
    )


@router.post("/requests", status_code=status.HTTP_201_CREATED)
async def create_request(
    payload: PurchaseRequestCreate, request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await PurchaseRequestService.create_request(session, payload, request)


@router.get("/requests/{pr_id}")
async def get_request(
    pr_id: str, request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await PurchaseRequestService.get_request(session, pr_id)


@router.patch("/requests/{pr_id}/transition")
async def transition_request(
    pr_id: str, payload: RequestStatusUpdate, request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await PurchaseRequestService.transition(session, pr_id, payload.action, request)


@router.get("/orders")
async def list_orders(
    request: Request,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    status_filter: str | None = Query(default=None, alias="status"),
    keyword: str | None = Query(default=None),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await PurchaseOrderService.list_orders(session, limit, offset, status_filter, keyword)


@router.post("/orders", status_code=status.HTTP_201_CREATED)
async def create_order(
    payload: PurchaseOrderCreate, request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await PurchaseOrderService.create_order(session, payload, request)


@router.get("/orders/{po_id}")
async def get_order(
    po_id: str, request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await PurchaseOrderService.get_order(session, po_id)


@router.patch("/orders/{po_id}/transition")
async def transition_order(
    po_id: str, payload: OrderStatusUpdate, request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await PurchaseOrderService.transition(session, po_id, payload.action, request)
