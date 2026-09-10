"""元信息路由：概览、指标、集成清单、安全基线。"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_session
from app.core.middleware import REQUEST_STATS
from app.services.item import ItemService

router = APIRouter(tags=["meta"])


@router.get("/api/overview")
async def overview(session: AsyncSession = Depends(get_session)) -> dict:
    item_stats = await ItemService.get_overview(session)
    return {
        "platform": {
            "name": settings.DISPLAY_NAME, "version": settings.VERSION,
            "description": settings.DESCRIPTION,
        },
        "items": item_stats["items"], "total": item_stats["total"], "active": item_stats["active"],
    }


@router.get("/api/ops/metrics")
async def ops_metrics() -> dict:
    total = int(REQUEST_STATS["total"])
    avg = round(float(REQUEST_STATS["latency_ms_total"]) / total, 2) if total else 0.0
    return {
        "service": settings.SERVICE_NAME, "version": settings.VERSION,
        "requests_total": total, "errors_total": int(REQUEST_STATS["errors"]),
        "avg_latency_ms": avg,
    }


@router.get("/api/integration/manifest")
async def integration_manifest() -> dict:
    return {
        "service": settings.SERVICE_NAME, "name": settings.DISPLAY_NAME,
        "version": settings.VERSION, "dependencies": settings.INTEGRATION_DEPENDENCIES,
        "events": settings.INTEGRATION_EVENTS, "health_path": "/health",
        "metrics_path": "/api/ops/metrics", "overview_path": "/api/overview",
    }


@router.get("/api/security/baseline")
async def security_baseline() -> dict:
    return {
        "service": settings.SERVICE_NAME, "version": settings.VERSION,
        "controls": {
            "trusted_host": True, "security_headers": True, "csp": True,
            "rate_limit": True, "request_size_limit": True, "sm3": True, "sm4": True,
            "internal_token": bool(settings.INTERNAL_API_KEY), "jwt": bool(settings.JWT_SECRET),
            "audit_persistence": True, "audit_forwarding": bool(settings.AUDIT_CENTER_URL),
        },
        "recommended": ["OIDC/MFA", "KMS/HSM", "centralized audit", "OpenTelemetry"],
    }
