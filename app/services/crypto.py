"""国密加解密服务。"""
from __future__ import annotations

from fastapi import HTTPException, status

from app.core.security import sm3_hex, sm4_crypt


class CryptoService:
    @staticmethod
    def sm3_hash(value: str) -> dict[str, str]:
        if len(value) > 10000:
            raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "内容过大")
        return {"algorithm": "SM3", "digest": sm3_hex(value)}

    @staticmethod
    def encrypt(value: str) -> dict[str, str]:
        if len(value) > 10000:
            raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "内容过大")
        return {"algorithm": "SM4-CBC", "ciphertext": sm4_crypt(value.encode("utf-8"), True).hex()}

    @staticmethod
    def decrypt(value_hex: str) -> dict[str, str]:
        try:
            value = bytes.fromhex(value_hex)
        except ValueError:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "密文必须是十六进制") from None
        return {"algorithm": "SM4-CBC", "plaintext": sm4_crypt(value, False).decode("utf-8")}

    @staticmethod
    def status() -> dict[str, object]:
        return {"algorithm": "SM3/SM4", "sm3": "enabled", "sm4": "enabled", "key_source": "SM4_KEY_HEX / persisted setting"}
