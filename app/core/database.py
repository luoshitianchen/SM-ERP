"""数据库层：SQLAlchemy 异步引擎，支持 PostgreSQL 与 SQLite。"""
from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings
from app.models.base import Base

# PostgreSQL 支持连接池，SQLite 使用默认 StaticPool
_engine_kwargs: dict = {"echo": settings.DB_ECHO, "pool_pre_ping": True}
if settings.effective_database_url.startswith("postgresql"):
    _engine_kwargs["pool_size"] = settings.DB_POOL_SIZE
    _engine_kwargs["max_overflow"] = settings.DB_MAX_OVERFLOW

engine = create_async_engine(settings.effective_database_url, **_engine_kwargs)

async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def init_db() -> None:
    """初始化数据库表结构（开发/测试用；生产用 Alembic）。"""
    import app.models  # noqa: F401
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI 依赖注入：获取数据库会话。"""
    async with async_session() as session:
        yield session
