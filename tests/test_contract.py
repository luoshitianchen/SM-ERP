"""服务契约测试：确保既有接口保留。"""
from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_integration_manifest(client):
    resp = await client.get("/api/integration/manifest")
    assert resp.status_code == 200
    data = resp.json()
    assert data["health_path"] == "/health"
    assert data["metrics_path"] == "/api/ops/metrics"
    assert data["overview_path"] == "/api/overview"


@pytest.mark.asyncio
async def test_ops_metrics(client):
    resp = await client.get("/api/ops/metrics")
    assert resp.status_code == 200
    assert "requests_total" in resp.json()


@pytest.mark.asyncio
async def test_prometheus_metrics(client):
    resp = await client.get("/metrics")
    assert resp.status_code == 200
    assert "text/plain" in resp.headers["content-type"]
    assert "requests_total" in resp.text


@pytest.mark.asyncio
async def test_security_baseline(client):
    resp = await client.get("/api/security/baseline")
    assert resp.status_code == 200
    assert resp.json()["controls"]["trusted_host"] is True
