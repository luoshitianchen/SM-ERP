"""ERP 采购域仓储：采购申请与采购订单异步数据访问。"""
from __future__ import annotations

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.purchase import PurchaseOrder, PurchaseRequest


async def get_request(session: AsyncSession, pr_id: str) -> PurchaseRequest | None:
    result = await session.execute(select(PurchaseRequest).where(PurchaseRequest.id == pr_id))
    return result.scalar_one_or_none()


async def get_request_by_code(session: AsyncSession, code: str) -> PurchaseRequest | None:
    result = await session.execute(select(PurchaseRequest).where(PurchaseRequest.code == code))
    return result.scalar_one_or_none()


async def list_requests(session: AsyncSession, limit: int, offset: int,
                       status: str | None = None, keyword: str | None = None) -> list[PurchaseRequest]:
    stmt = select(PurchaseRequest).order_by(PurchaseRequest.created_at.desc()).limit(limit).offset(offset)
    if status:
        stmt = stmt.where(PurchaseRequest.status == status)
    if keyword:
        like = f"%{keyword}%"
        stmt = stmt.where(or_(PurchaseRequest.title.like(like), PurchaseRequest.code.like(like)))
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def count_requests(session: AsyncSession, status: str | None = None,
                        keyword: str | None = None) -> int:
    stmt = select(func.count(PurchaseRequest.id))
    if status:
        stmt = stmt.where(PurchaseRequest.status == status)
    if keyword:
        like = f"%{keyword}%"
        stmt = stmt.where(or_(PurchaseRequest.title.like(like), PurchaseRequest.code.like(like)))
    return int((await session.execute(stmt)).scalar_one())


async def create_request(session: AsyncSession, pr: PurchaseRequest) -> PurchaseRequest:
    session.add(pr)
    await session.commit()
    await session.refresh(pr)
    return pr


async def update_request(session: AsyncSession, pr: PurchaseRequest) -> PurchaseRequest:
    await session.commit()
    await session.refresh(pr)
    return pr


async def get_order(session: AsyncSession, po_id: str) -> PurchaseOrder | None:
    result = await session.execute(select(PurchaseOrder).where(PurchaseOrder.id == po_id))
    return result.scalar_one_or_none()


async def get_order_by_number(session: AsyncSession, po_number: str) -> PurchaseOrder | None:
    result = await session.execute(select(PurchaseOrder).where(PurchaseOrder.po_number == po_number))
    return result.scalar_one_or_none()


async def list_orders(session: AsyncSession, limit: int, offset: int,
                     status: str | None = None, keyword: str | None = None) -> list[PurchaseOrder]:
    stmt = select(PurchaseOrder).order_by(PurchaseOrder.created_at.desc()).limit(limit).offset(offset)
    if status:
        stmt = stmt.where(PurchaseOrder.status == status)
    if keyword:
        like = f"%{keyword}%"
        stmt = stmt.where(or_(PurchaseOrder.po_number.like(like), PurchaseOrder.supplier.like(like)))
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def count_orders(session: AsyncSession, status: str | None = None,
                       keyword: str | None = None) -> int:
    stmt = select(func.count(PurchaseOrder.id))
    if status:
        stmt = stmt.where(PurchaseOrder.status == status)
    if keyword:
        like = f"%{keyword}%"
        stmt = stmt.where(or_(PurchaseOrder.po_number.like(like), PurchaseOrder.supplier.like(like)))
    return int((await session.execute(stmt)).scalar_one())


async def count_orders_by_pr(session: AsyncSession, pr_id: str) -> int:
    stmt = select(func.count(PurchaseOrder.id)).where(PurchaseOrder.pr_id == pr_id)
    return int((await session.execute(stmt)).scalar_one())


async def create_order(session: AsyncSession, po: PurchaseOrder) -> PurchaseOrder:
    session.add(po)
    await session.commit()
    await session.refresh(po)
    return po


async def update_order(session: AsyncSession, po: PurchaseOrder) -> PurchaseOrder:
    await session.commit()
    await session.refresh(po)
    return po
