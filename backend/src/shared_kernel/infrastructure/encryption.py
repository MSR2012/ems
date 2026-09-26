"""Fernet-based TokenCipher (MultiFernet: first key encrypts, all keys decrypt → rotation)."""

from __future__ import annotations

from cryptography.fernet import Fernet, InvalidToken, MultiFernet
from django.conf import settings


class TokenDecryptionError(Exception):
    pass


class FernetTokenCipher:
    def __init__(self, keys: list[str] | None = None) -> None:
        keys = keys if keys is not None else list(settings.TOKEN_ENCRYPTION_KEYS)
        if not keys:
            raise RuntimeError("TOKEN_ENCRYPTION_KEY is not configured")
        self._fernet = MultiFernet([Fernet(k.encode() if isinstance(k, str) else k) for k in keys])

    def encrypt(self, plaintext: str) -> str:
        return self._fernet.encrypt(plaintext.encode()).decode()

    def decrypt(self, ciphertext: str) -> str:
        try:
            return self._fernet.decrypt(ciphertext.encode()).decode()
        except InvalidToken as exc:
            raise TokenDecryptionError("could not decrypt token") from exc

    def rotate(self, ciphertext: str) -> str:
        return self._fernet.rotate(ciphertext.encode()).decode()
