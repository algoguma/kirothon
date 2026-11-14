"""Shared API dependencies: DB session and the logged-in user from the session cookie."""

from typing import Annotated

from cryptography.fernet import InvalidToken
from fastapi import Cookie, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.crypto import decrypt
from app.db import get_db
from app.errors import ApiError
from app.models import User

SESSION_COOKIE = "session"
SESSION_MAX_AGE_SEC = 7 * 24 * 3600

DbSession = Annotated[AsyncSession, Depends(get_db)]


async def get_current_user(db: DbSession, session: Annotated[str | None, Cookie()] = None) -> User:
    unauthorized = ApiError(401, "UNAUTHORIZED", "로그인이 필요합니다.")
    if not session:
        raise unauthorized
    try:
        user_id = int(decrypt(session.encode(), ttl=SESSION_MAX_AGE_SEC))
    except (InvalidToken, ValueError):
        raise unauthorized from None
    # Logged-out users keep their row (LLM key stays) but have no Telegram session.
    user = await db.scalar(
        select(User).where(User.id == user_id, User.encrypted_session.is_not(None))
    )
    if user is None:
        raise unauthorized
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
