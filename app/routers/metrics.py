"""Prometheus 指标端点。"""
from __future__ import annotations

import threading
from collections import defaultdict

from fastapi import APIRouter, Response

from app.core.config import settings

router = APIRouter(tags=["metrics"])

PREFIX = settings.SERVICE_NAME.replace("-", "_")

_prom_stats = {
    "requests_total": 0, "errors_total": 0,
    "latency_ms_total": 0.0, "status_counts": defaultdict(int),
}
_prom_lock = threading.Lock()


def record_request(status_code: int, latency_ms: float) -> None:
    with _prom_lock:
        _prom_stats["requests_total"] += 1
        _prom_stats["latency_ms_total"] += latency_ms
        _prom_stats["status_counts"][str(status_code)] += 1
        if status_code >= 500:
            _prom_stats["errors_total"] += 1


@router.get("/metrics")
async def prometheus_metrics() -> Response:
    with _prom_lock:
        total = _prom_stats["requests_total"]
        errors = _prom_stats["errors_total"]
        latency = _prom_stats["latency_ms_total"]
        status_lines = "\n".join(
            f'{PREFIX}_http_requests_total{{status="{code}"}} {count}'
            for code, count in sorted(_prom_stats["status_counts"].items())
        )
    body = (
        f"# HELP {PREFIX}_requests_total Total HTTP requests\n"
        f"# TYPE {PREFIX}_requests_total counter\n"
        f"{PREFIX}_requests_total {total}\n"
        f"# HELP {PREFIX}_errors_total Total HTTP 5xx errors\n"
        f"# TYPE {PREFIX}_errors_total counter\n"
        f"{PREFIX}_errors_total {errors}\n"
        f"# HELP {PREFIX}_latency_ms_total Total request latency in ms\n"
        f"# TYPE {PREFIX}_latency_ms_total counter\n"
        f"{PREFIX}_latency_ms_total {latency:.2f}\n"
        f"# HELP {PREFIX}_http_requests_total HTTP requests by status code\n"
        f"# TYPE {PREFIX}_http_requests_total counter\n"
        f"{status_lines}\n"
    )
    return Response(content=body, media_type="text/plain; version=0.0.4")
