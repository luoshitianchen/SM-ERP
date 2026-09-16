"""ERP 库存域路由：库存物料与出入库流水。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.schemas.inventory import StockItemCreate, StockItemUpdate, StockTransactionCreate
from app.services.inventory import InventoryTransactionService, StockItemService

router = APIRouter(prefix="/api/inventory", tags=["erp-inventory"])


@router.get("/items")
async def list_items(
    request: Request,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    status_filter: str | None = Query(default=None, alias="status"),
    keyword: str | None = Query(default=None),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await StockItemService.list_items(session, limit, offset, status_filter, keyword)


@router.post("/items", status_code=status.HTTP_201_CREATED)
async def create_item(
    payload: StockItemCreate, request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await StockItemService.create_item(session, payload, request)


@router.get("/items/{item_id}")
async def get_item(
    item_id: str, request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await StockItemService.get_item(session, item_id)


@router.patch("/items/{item_id}")
async def update_item(
    item_id: str, payload: StockItemUpdate, request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await StockItemService.update_item(session, item_id, payload, request)


@router.get("/transactions")
async def list_transactions(
    request: Request,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    stock_item_id: str | None = Query(default=None),
    direction: str | None = Query(default=None),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await InventoryTransactionService.list_transactions(
        session, limit, offset, stock_item_id, direction
    )


@router.post("/transactions", status_code=status.HTTP_201_CREATED)
async def apply_transaction(
    payload: StockTransactionCreate, request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await InventoryTransactionService.apply_transaction(session, payload, request)
