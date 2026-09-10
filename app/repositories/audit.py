"""审计事件仓储。"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_event import AuditEvent


async def create_audit_event(session: AsyncSession, event: AuditEvent) -> AuditEvent:
    session.add(event)
    await session.commit()
    await session.refresh(event)
    return event


async def list_audit_events(session: AsyncSession, limit: int = 200) -> list[AuditEvent]:
    result = await session.execute(
        select(AuditEvent).order_by(AuditEvent.id.desc()).limit(limit)
    )
    return list(result.scalars().all())
