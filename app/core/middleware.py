"""安全中间件：统一安全响应头、限流、请求体限制、指标采集。"""
from __future__ import annotations

import time
import uuid
from collections.abc import Awaitable, Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import settings
from app.core.security import PUBLIC_PATHS, authorized, check_rate_limit
from app.routers.metrics import record_request

REQUEST_STATS = {"total": 0, "errors": 0, "latency_ms_total": 0.0}


class SecurityMiddleware(BaseHTTPMiddleware):
    """统一安全中间件。"""

    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        started = time.perf_counter()
        request_id = request.headers.get("X-Request-Id") or str(uuid.uuid4())
        trace_id = request.headers.get("X-Trace-Id") or str(uuid.uuid4())
        request.state.request_id = request_id[:64]
        request.state.trace_id = trace_id[:64]

        path = request.url.path
        if path.startswith("/api/") and path not in PUBLIC_PATHS and not authorized(request):
            response = Response(status_code=401, content="认证无效")
        else:
            content_length = request.headers.get("content-length")
            if content_length:
                try:
                    body_size = int(content_length)
                except ValueError:
                    response = Response(status_code=400, content="Invalid Content-Length")
                else:
                    if body_size < 0 or body_size > settings.MAX_REQUEST_BYTES:
                        response = Response(status_code=413, content="Request body too large")
                    elif not self._check_rate(request):
                        response = self._rate_limited()
                    else:
                        response = await call_next(request)
            elif not self._check_rate(request):
                response = self._rate_limited()
            else:
                response = await call_next(request)

        elapsed = (time.perf_counter() - started) * 1000
        REQUEST_STATS["total"] += 1
        REQUEST_STATS["latency_ms_total"] += elapsed
        if response.status_code >= 500:
            REQUEST_STATS["errors"] += 1
        record_request(response.status_code, elapsed)

        response.headers["X-Request-Id"] = request_id[:64]
        response.headers["X-Trace-Id"] = trace_id[:64]
        response.headers["X-Process-Time-Ms"] = f"{elapsed:.2f}"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=(), payment=(), usb=()"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; style-src 'self' 'unsafe-inline'; "
            "script-src 'self' 'unsafe-inline'; connect-src 'self'; "
            "img-src 'self' data:; base-uri 'self'; form-action 'self'; frame-ancestors 'none'"
        )
        if settings.is_production:
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Cache-Control"] = "no-store" if path.startswith("/api/") else "no-cache"
        return response

    def _check_rate(self, request: Request) -> bool:
        client_host = request.client.host if request.client else "unknown"
        return check_rate_limit(f"{client_host}:{request.url.path}")

    def _rate_limited(self) -> Response:
        return Response(
            status_code=429, content="Too many requests",
            headers={"Retry-After": str(settings.RATE_WINDOW_SECONDS)},
        )
