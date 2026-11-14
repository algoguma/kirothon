"""Fernet encryption for Telethon sessions, Telegram api_hash and LLM API keys."""

from functools import lru_cache

from cryptography.fernet import Fernet

from app.config import get_settings


@lru_cache
def _fernet() -> Fernet:
    key = get_settings().encryption_key
    if not key:
        raise RuntimeError("ENCRYPTION_KEY is not set in backend/.env")
    return Fernet(key)


def check_key() -> None:
    """Raise if ENCRYPTION_KEY is missing or malformed."""
    _fernet()


def encrypt(plain: str) -> bytes:
    return _fernet().encrypt(plain.encode())


def decrypt(token: bytes, ttl: int | None = None) -> str:
    """Raise cryptography.fernet.InvalidToken if tampered or older than `ttl` seconds."""
    return _fernet().decrypt(token, ttl=ttl).decode()
