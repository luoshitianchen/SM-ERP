"""安全模块：国密 SM3/SM4、JWT、限流、内部令牌校验。"""
from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import json
import secrets
import threading
import time

from fastapi import Request

from app.core.config import settings

# ── 限流 ──
_rate_buckets: dict[str, tuple[int, int]] = {}
_rate_lock = threading.Lock()


def check_rate_limit(key: str) -> bool:
    """令牌桶限流。返回 True 允许，False 超限。"""
    with _rate_lock:
        current = int(time.time())
        for bucket_key, (started, _) in list(_rate_buckets.items()):
            if current - started >= settings.RATE_WINDOW_SECONDS:
                _rate_buckets.pop(bucket_key, None)
        started, count = _rate_buckets.get(key, (current, 0))
        if current - started >= settings.RATE_WINDOW_SECONDS:
            started, count = current, 0
        if count >= settings.RATE_MAX_REQUESTS:
            return False
        _rate_buckets[key] = (started, count + 1)
        return True


# ── 内部令牌 ──
def internal_write_allowed(request: Request) -> bool:
    """校验内部服务写入令牌 (X-Internal-Token)。"""
    if not settings.INTERNAL_API_KEY:
        return False
    return secrets.compare_digest(
        request.headers.get("X-Internal-Token", ""), settings.INTERNAL_API_KEY
    )


# ── 国密 SM3 ──
def sm3_hex(value: str) -> str:
    """计算 SM3 哈希摘要（十六进制）。"""
    from gmssl import func, sm3
    return sm3.sm3_hash(func.bytes_to_list(value.encode("utf-8")))


# ── 国密 SM4 ──
def _sm4_key() -> bytes:
    """获取 SM4 密钥：优先环境变量，否则从数据库 settings 读取/生成。"""
    if settings.SM4_KEY_HEX:
        key = bytes.fromhex(settings.SM4_KEY_HEX)
        if len(key) == 16:
            return key
    from app.core.database import async_session
    from app.repositories.setting_repo import get_setting, set_setting

    async def _ensure():
        async with async_session() as session:
            existing = await get_setting(session, "sm4_key_hex")
            if not existing:
                existing = secrets.token_hex(16)
                await set_setting(session, "sm4_key_hex", existing)
            return existing

    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            return asyncio.run_coroutine_threadsafe(_ensure(), loop).result(timeout=5)
        return loop.run_until_complete(_ensure())
    except RuntimeError:
        return asyncio.run(_ensure())


def sm4_crypt(value: bytes, encrypt: bool) -> bytes:
    """SM4-CBC 加解密。加密时随机生成 IV 并前置到密文。"""
    from gmssl.sm4 import SM4_DECRYPT, SM4_ENCRYPT, CryptSM4
    cipher = CryptSM4()
    key = _sm4_key()
    if encrypt:
        iv = secrets.token_bytes(16)
        cipher.set_key(key, SM4_ENCRYPT)
        return iv + cipher.crypt_cbc(iv, value)
    if len(value) < 16:
        raise ValueError("ciphertext too short")
    iv, body = value[:16], value[16:]
    cipher.set_key(key, SM4_DECRYPT)
    return cipher.crypt_cbc(iv, body)


# ── JWT ──
def b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def b64url_decode(data: str) -> bytes:
    return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))


def _jwt_secret() -> str:
    """获取 JWT 签名密钥：优先环境变量，否则从持久化设置读取/生成。"""
    if settings.JWT_SECRET:
        return settings.JWT_SECRET
    from app.core.database import async_session
    from app.repositories.setting_repo import get_setting, set_setting

    async def _ensure():
        async with async_session() as session:
            existing = await get_setting(session, "jwt_secret")
            if not existing:
                existing = secrets.token_hex(32)
                await set_setting(session, "jwt_secret", existing)
            return existing

    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            return asyncio.run_coroutine_threadsafe(_ensure(), loop).result(timeout=5)
        return loop.run_until_complete(_ensure())
    except RuntimeError:
        return asyncio.run(_ensure())



def verify_jwt(token: str) -> dict[str, object] | None:
    """验证 JWT (HS256)，返回 claims 或 None。"""
    try:
        header_b64, claims_b64, signature_b64 = token.split(".")
        signing_input = f"{header_b64}.{claims_b64}".encode()
        expected = hmac.new(_jwt_secret().encode(), signing_input, hashlib.sha256).digest()
        if not hmac.compare_digest(expected, b64url_decode(signature_b64)):
            return None
        claims = json.loads(b64url_decode(claims_b64))
        if int(claims.get("exp", 0)) < time.time():
            return None
        if claims.get("iss") != settings.SERVICE_NAME:
            return None
        return claims
    except Exception:
        return None


# ── 认证辅助 ──
PUBLIC_PATHS = {
    "/api/overview", "/api/crypto/status", "/api/crypto/sm3",
    "/api/crypto/encrypt", "/api/crypto/decrypt",
    "/api/ops/metrics", "/api/integration/manifest", "/api/security/baseline",
}


def authorized(request: Request) -> bool:
    """请求认证检查：内部令牌直通，否则校验 Bearer JWT。"""
    if internal_write_allowed(request):
        return True
    if not (settings.JWT_SECRET or settings.INTERNAL_API_KEY):
        return True
    authorization = request.headers.get("Authorization", "")
    return authorization.startswith("Bearer ") and verify_jwt(authorization[7:]) is not None
