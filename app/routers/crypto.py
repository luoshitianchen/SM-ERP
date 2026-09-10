"""国密加解密路由。"""
from __future__ import annotations

from fastapi import APIRouter

from app.schemas.common import CryptoRequest
from app.services.crypto import CryptoService

router = APIRouter(prefix="/api/crypto", tags=["crypto"])


@router.post("/sm3")
async def crypto_sm3(payload: CryptoRequest) -> dict:
    return CryptoService.sm3_hash(payload.value)


@router.post("/encrypt")
async def crypto_encrypt(payload: CryptoRequest) -> dict:
    return CryptoService.encrypt(payload.value)


@router.post("/decrypt")
async def crypto_decrypt(payload: CryptoRequest) -> dict:
    return CryptoService.decrypt(payload.value)


@router.get("/status")
async def crypto_status() -> dict:
    return CryptoService.status()
