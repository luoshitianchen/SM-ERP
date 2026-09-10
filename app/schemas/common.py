"""通用响应模型。"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str
    service: str
    name: str
    version: str
    timestamp: str


class ReadyResponse(BaseModel):
    status: str
    service: str
    checks: dict[str, str]


class MetricsResponse(BaseModel):
    service: str
    version: str
    requests_total: int
    errors_total: int
    avg_latency_ms: float


class IntegrationManifest(BaseModel):
    service: str
    name: str
    version: str
    dependencies: list[str]
    events: list[str]
    health_path: str
    metrics_path: str
    overview_path: str


class SecurityBaseline(BaseModel):
    service: str
    version: str
    controls: dict[str, Any]
    recommended: list[str]


class CryptoRequest(BaseModel):
    value: str = Field(max_length=10000)


class CryptoSm3Response(BaseModel):
    algorithm: str
    digest: str


class CryptoEncryptResponse(BaseModel):
    algorithm: str
    ciphertext: str


class CryptoDecryptResponse(BaseModel):
    algorithm: str
    plaintext: str


class CryptoStatusResponse(BaseModel):
    algorithm: str
    sm3: str
    sm4: str
    key_source: str
