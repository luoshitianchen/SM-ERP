"""国密加解密测试。"""
from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_sm3_hash(client):
    resp = await client.post("/api/crypto/sm3", json={"value": "hello"})
    assert resp.status_code == 200
    assert len(resp.json()["digest"]) == 64


@pytest.mark.asyncio
async def test_sm4_roundtrip(client):
    plaintext = "生产级敏感数据"
    enc = await client.post("/api/crypto/encrypt", json={"value": plaintext})
    assert enc.status_code == 200
    ct = enc.json()["ciphertext"]
    dec = await client.post("/api/crypto/decrypt", json={"value": ct})
    assert dec.status_code == 200
    assert dec.json()["plaintext"] == plaintext


@pytest.mark.asyncio
async def test_crypto_status(client):
    resp = await client.get("/api/crypto/status")
    assert resp.status_code == 200
    assert resp.json()["sm3"] == "enabled"
