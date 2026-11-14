"""Fernet encryption for Telethon sessions and LLM API keys."""

from functools import lru_cache

from cryptography.fernet import Fernet

from app.config import get_settings


@lru_cache
def _fernet() -> Fernet:
    key = get_settings().encryption_key
    if not key:
        raise RuntimeError("ENCRYPTION_KEY is not set in backend/.env")
    return Fernet(key)


def encrypt(plain: str) -> bytes:
    return _fernet().encrypt(plain.encode())


def decrypt(token: bytes) -> str:
    return _fernet().decrypt(token).decode()
