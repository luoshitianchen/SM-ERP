"""应用配置：基于 pydantic-settings 的类型安全配置管理。

所有配置项均可通过环境变量覆盖，密钥类配置禁止硬编码。
"""
from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """服务配置类。环境变量前缀 SM_。"""

    model_config = SettingsConfigDict(
        env_prefix="SM_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── 服务元数据 ──
    VERSION: str = "2.5.0"
    SERVICE_NAME: str = "sm-erp"
    DISPLAY_NAME: str = "SM ERP"
    DESCRIPTION: str = "企业资源与身份管理系统"

    # ── 运行环境 ──
    ENV: str = Field(default="development")
    LOG_LEVEL: str = Field(default="INFO")
    LOG_FORMAT: str = Field(default="json")

    # ── 网络与安全 ──
    ALLOWED_HOSTS: list[str] = Field(
        default_factory=lambda: ["localhost", "127.0.0.1", "testserver"]
    )
    MAX_REQUEST_BYTES: int = Field(default=1048576)
    RATE_WINDOW_SECONDS: int = Field(default=60)
    RATE_MAX_REQUESTS: int = Field(default=600)

    # ── 认证与密钥 ──
    INTERNAL_API_KEY: str = Field(default="")
    JWT_SECRET: str = Field(default="")
    JWT_TTL_SECONDS: int = Field(default=3600)
    SM4_KEY_HEX: str = Field(default="")

    # ── 数据库 ──
    DATABASE_URL: str = Field(default="sqlite+aiosqlite:///./data.db")
    DATABASE_PATH: str = Field(default="")
    DB_POOL_SIZE: int = Field(default=10)
    DB_MAX_OVERFLOW: int = Field(default=20)
    DB_ECHO: bool = Field(default=False)

    # ── ERP 特有 ──
    ERP_BOOTSTRAP_PASSWORD: str = Field(default="")

    # ── 集成 ──
    AUDIT_CENTER_URL: str = Field(default="")
    INTEGRATION_DEPENDENCIES: list[str] = Field(default_factory=lambda: ['sm-iam', 'sm-audit-log-center'])
    INTEGRATION_EVENTS: list[str] = Field(default_factory=lambda: ['health.checked', 'resource.changed', 'audit.recorded'])


    @property
    def is_production(self) -> bool:
        return self.ENV.lower() == "production"

    @property
    def effective_database_url(self) -> str:
        if self.DATABASE_PATH and not self.DATABASE_URL.startswith("postgresql"):
            return f"sqlite+aiosqlite:///{self.DATABASE_PATH}"
        return self.DATABASE_URL


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
