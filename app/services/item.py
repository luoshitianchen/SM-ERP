"""业务项服务层。"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import internal_write_allowed
from app.models.item import Item
from app.repositories.item import (
    count_active_items,
    count_items,
    get_item,
    list_items,
)
from app.repositories.item import (
    create_item as repo_create,
)
from app.repositories.item import (
    update_item_status as repo_update,
)
from app.schemas.item import ItemCreate
from app.services.audit import record_audit


class ItemService:
    @staticmethod
    async def get_overview(session: AsyncSession) -> dict:
        items = await list_items(session, limit=100)
        total = await count_items(session)
        active = await count_active_items(session)
        return {
            "items": [
                {
                    "id": i.id, "name": i.name, "owner": i.owner,
                    "priority": i.priority, "status": i.status,
                    "created_at": i.created_at.isoformat() if i.created_at else "",
                }
                for i in items
            ],
            "total": total, "active": active,
        }

    @staticmethod
    async def create(session: AsyncSession, payload: ItemCreate, request: Request) -> dict:
        if not internal_write_allowed(request):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "内部写入令牌无效")
        item = Item(id=str(uuid.uuid4()), name=payload.name, owner=payload.owner,
                    priority=payload.priority, status=payload.status)
        item = await repo_create(session, item)
        await record_audit(session, "resource.created", "internal",
                           f"id={item.id} name={payload.name}", request)
        return {
            "id": item.id, "name": item.name, "owner": item.owner,
            "priority": item.priority, "status": item.status,
            "created_at": item.created_at.isoformat() if item.created_at else datetime.now(UTC).isoformat(),
        }

    @staticmethod
    async def update_status(session: AsyncSession, item_id: str, new_status: str, request: Request) -> dict:
        if not internal_write_allowed(request):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "内部写入令牌无效")
        item = await get_item(session, item_id)
        if not item:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "资源不存在")
        item = await repo_update(session, item, new_status)
        await record_audit(session, "resource.status_changed", "internal",
                           f"id={item_id} status={new_status}", request)
        return {
            "id": item.id, "name": item.name, "owner": item.owner,
            "priority": item.priority, "status": item.status,
            "created_at": item.created_at.isoformat() if item.created_at else "",
        }
