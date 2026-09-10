"""业务项仓储。"""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.item import Item


async def get_item(session: AsyncSession, item_id: str) -> Item | None:
    result = await session.execute(select(Item).where(Item.id == item_id))
    return result.scalar_one_or_none()


async def list_items(session: AsyncSession, limit: int = 100) -> list[Item]:
    result = await session.execute(select(Item).order_by(Item.created_at.desc()).limit(limit))
    return list(result.scalars().all())


async def create_item(session: AsyncSession, item: Item) -> Item:
    session.add(item)
    await session.commit()
    await session.refresh(item)
    return item


async def update_item_status(session: AsyncSession, item: Item, status: str) -> Item:
    item.status = status
    await session.commit()
    await session.refresh(item)
    return item


async def count_items(session: AsyncSession) -> int:
    result = await session.execute(select(func.count(Item.id)))
    return int(result.scalar_one())


async def count_active_items(session: AsyncSession) -> int:
    result = await session.execute(select(func.count(Item.id)).where(Item.status == "active"))
    return int(result.scalar_one())
