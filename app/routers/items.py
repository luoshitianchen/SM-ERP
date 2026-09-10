"""业务项 CRUD 路由。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.schemas.item import ItemCreate, ItemStatusUpdate
from app.services.item import ItemService

router = APIRouter(prefix="/api/items", tags=["items"])


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_item(
    payload: ItemCreate, request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await ItemService.create(session, payload, request)


@router.patch("/{item_id}/status")
async def update_item_status(
    item_id: str, payload: ItemStatusUpdate, request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await ItemService.update_status(session, item_id, payload.status, request)
