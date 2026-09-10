"""应用入口：创建 FastAPI 实例并注册中间件与路由。"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import FileResponse

from app.core.config import settings
from app.core.database import init_db
from app.core.logging import setup_logging
from app.core.middleware import SecurityMiddleware
from app.routers import crypto, employees, health, items, meta, metrics

setup_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期：启动时初始化数据库，关闭时释放连接。"""
    await init_db()
    yield
    from app.core.database import engine
    await engine.dispose()


app = FastAPI(
    title=settings.DISPLAY_NAME,
    version=settings.VERSION,
    description=settings.DESCRIPTION,
    docs_url=None,
    redoc_url=None,
    lifespan=lifespan,
)

app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.ALLOWED_HOSTS)
app.add_middleware(SecurityMiddleware)

app.include_router(health.router)
app.include_router(meta.router)
app.include_router(crypto.router)
app.include_router(items.router)
app.include_router(metrics.router)
app.include_router(employees.router)



@app.get("/", include_in_schema=False)
def console() -> FileResponse:
    """控制台静态页面。"""
    return FileResponse("app/static/index.html")
