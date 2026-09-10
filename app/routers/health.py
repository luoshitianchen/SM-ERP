"""健康检查与就绪探针路由。"""
from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter

from app.core.config import settings

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict:
    return {
        "status": "ok", "service": settings.SERVICE_NAME,
        "name": settings.DISPLAY_NAME, "version": settings.VERSION,
        "timestamp": datetime.now(UTC).isoformat(),
    }


@router.get("/readyz")
async def readyz() -> dict:
    db_ok = True
    try:
        from sqlalchemy import text

        from app.core.database import async_session
        async with async_session() as session:
            await session.execute(text("SELECT 1"))
    except Exception:
        db_ok = False
    return {
        "status": "ready" if db_ok else "degraded",
        "service": settings.SERVICE_NAME,
        "checks": {"runtime": "ok", "configuration": "ok", "database": "ok" if db_ok else "error"},
    }
