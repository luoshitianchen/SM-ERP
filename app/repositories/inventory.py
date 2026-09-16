"""ERP 库存域仓储：库存物料与库存流水异步数据访问。"""
from __future__ import annotations

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.inventory import InventoryTransaction, StockItem


async def get_item(session: AsyncSession, item_id: str) -> StockItem | None:
    result = await session.execute(select(StockItem).where(StockItem.id == item_id))
    return result.scalar_one_or_none()


async def get_item_by_sku(session: AsyncSession, sku: str) -> StockItem | None:
    result = await session.execute(select(StockItem).where(StockItem.sku == sku))
    return result.scalar_one_or_none()


async def list_items(session: AsyncSession, limit: int, offset: int,
                    status: str | None = None, keyword: str | None = None) -> list[StockItem]:
    stmt = select(StockItem).order_by(StockItem.created_at.desc()).limit(limit).offset(offset)
    if status:
        stmt = stmt.where(StockItem.status == status)
    if keyword:
        like = f"%{keyword}%"
        stmt = stmt.where(or_(StockItem.name.like(like), StockItem.sku.like(like)))
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def count_items(session: AsyncSession, status: str | None = None,
                      keyword: str | None = None) -> int:
    stmt = select(func.count(StockItem.id))
    if status:
        stmt = stmt.where(StockItem.status == status)
    if keyword:
        like = f"%{keyword}%"
        stmt = stmt.where(or_(StockItem.name.like(like), StockItem.sku.like(like)))
    return int((await session.execute(stmt)).scalar_one())


async def create_item(session: AsyncSession, item: StockItem) -> StockItem:
    session.add(item)
    await session.commit()
    await session.refresh(item)
    return item


async def update_item(session: AsyncSession, item: StockItem) -> StockItem:
    await session.commit()
    await session.refresh(item)
    return item


async def list_transactions(session: AsyncSession, limit: int, offset: int,
                            stock_item_id: str | None = None,
                            direction: str | None = None) -> list[InventoryTransaction]:
    stmt = select(InventoryTransaction).order_by(
        InventoryTransaction.created_at.desc()
    ).limit(limit).offset(offset)
    if stock_item_id:
        stmt = stmt.where(InventoryTransaction.stock_item_id == stock_item_id)
    if direction:
        stmt = stmt.where(InventoryTransaction.direction == direction)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def count_transactions(session: AsyncSession, stock_item_id: str | None = None,
                             direction: str | None = None) -> int:
    stmt = select(func.count(InventoryTransaction.id))
    if stock_item_id:
        stmt = stmt.where(InventoryTransaction.stock_item_id == stock_item_id)
    if direction:
        stmt = stmt.where(InventoryTransaction.direction == direction)
    return int((await session.execute(stmt)).scalar_one())


async def create_transaction(session: AsyncSession, tx: InventoryTransaction) -> InventoryTransaction:
    session.add(tx)
    await session.commit()
    await session.refresh(tx)
    return tx
