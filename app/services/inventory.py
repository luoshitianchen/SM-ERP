"""ERP 库存域服务：物料建档、出入库流水与库存余额校验。"""
from __future__ import annotations

import uuid

from fastapi import HTTPException, Request, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import internal_write_allowed
from app.models.inventory import InventoryTransaction, StockItem
from app.repositories import inventory as repo
from app.schemas.inventory import StockItemCreate, StockItemUpdate, StockTransactionCreate
from app.services.audit import record_audit


def _item_to_dict(item: StockItem) -> dict:
    return {
        "id": item.id, "sku": item.sku, "name": item.name, "unit": item.unit,
        "quantity": item.quantity, "safety_stock": item.safety_stock,
        "unit_price": item.unit_price, "status": item.status,
        # 低库存告警：当前库存低于安全库存阈值
        "low_stock": item.quantity < item.safety_stock,
        "created_at": item.created_at.isoformat() if item.created_at else "",
        "updated_at": item.updated_at.isoformat() if item.updated_at else "",
    }


def _tx_to_dict(tx: InventoryTransaction) -> dict:
    return {
        "id": tx.id, "stock_item_id": tx.stock_item_id, "direction": tx.direction,
        "change_qty": tx.change_qty, "remark": tx.remark, "operator_id": tx.operator_id,
        "created_at": tx.created_at.isoformat() if tx.created_at else "",
    }


class StockItemService:
    @staticmethod
    async def list_items(session: AsyncSession, limit: int, offset: int,
                         status_filter: str | None, keyword: str | None) -> dict:
        rows = await repo.list_items(session, limit, offset, status_filter, keyword)
        total = await repo.count_items(session, status_filter, keyword)
        return {"total": total, "items": [_item_to_dict(i) for i in rows]}

    @staticmethod
    async def get_item(session: AsyncSession, item_id: str) -> dict:
        item = await repo.get_item(session, item_id)
        if not item:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "库存物料不存在")
        return _item_to_dict(item)

    @staticmethod
    async def create_item(session: AsyncSession, payload: StockItemCreate,
                          request: Request) -> dict:
        if not internal_write_allowed(request):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "内部写入令牌无效")
        if await repo.get_item_by_sku(session, payload.sku):
            raise HTTPException(status.HTTP_409_CONFLICT, "SKU 已存在")
        item = StockItem(
            id=str(uuid.uuid4()), sku=payload.sku, name=payload.name, unit=payload.unit,
            quantity=payload.quantity, safety_stock=payload.safety_stock,
            unit_price=payload.unit_price, status="active",
        )
        try:
            item = await repo.create_item(session, item)
        except IntegrityError as exc:
            raise HTTPException(status.HTTP_409_CONFLICT, "SKU 已存在") from exc
        await record_audit(session, "stock_item.created", "internal",
                           f"item_id={item.id} sku={payload.sku}", request)
        return _item_to_dict(item)

    @staticmethod
    async def update_item(session: AsyncSession, item_id: str, payload: StockItemUpdate,
                          request: Request) -> dict:
        if not internal_write_allowed(request):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "内部写入令牌无效")
        item = await repo.get_item(session, item_id)
        if not item:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "库存物料不存在")
        for field in ("name", "unit", "safety_stock", "unit_price", "status"):
            value = getattr(payload, field)
            if value is not None:
                setattr(item, field, value)
        item = await repo.update_item(session, item)
        await record_audit(session, "stock_item.updated", "internal",
                           f"item_id={item_id}", request)
        return _item_to_dict(item)


class InventoryTransactionService:
    @staticmethod
    async def list_transactions(session: AsyncSession, limit: int, offset: int,
                                stock_item_id: str | None, direction: str | None) -> dict:
        rows = await repo.list_transactions(session, limit, offset, stock_item_id, direction)
        total = await repo.count_transactions(session, stock_item_id, direction)
        return {"total": total, "items": [_tx_to_dict(t) for t in rows]}

    @staticmethod
    async def apply_transaction(session: AsyncSession, payload: StockTransactionCreate,
                                request: Request) -> dict:
        if not internal_write_allowed(request):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "内部写入令牌无效")
        item = await repo.get_item(session, payload.stock_item_id)
        if not item:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "库存物料不存在")
        if item.status != "active":
            raise HTTPException(status.HTTP_409_CONFLICT, "物料非启用状态，不允许出入库")
        # 业务规则：出库后库存不得为负
        if payload.direction == "out" and item.quantity < payload.change_qty:
            raise HTTPException(status.HTTP_409_CONFLICT,
                               f"库存不足：当前 {item.quantity}，申请出库 {payload.change_qty}")
        if payload.direction == "in":
            item.quantity += payload.change_qty
        else:
            item.quantity -= payload.change_qty
        tx = InventoryTransaction(
            id=str(uuid.uuid4()), stock_item_id=item.id, direction=payload.direction,
            change_qty=payload.change_qty, remark=payload.remark,
            operator_id=payload.operator_id,
        )
        await repo.create_transaction(session, tx)
        await repo.update_item(session, item)
        await record_audit(session, "inventory.transaction", "internal",
                           f"item_id={item.id} direction={payload.direction} qty={payload.change_qty}",
                           request)
        return {
            "transaction": _tx_to_dict(tx),
            "quantity": item.quantity,
            "low_stock": item.quantity < item.safety_stock,
        }
