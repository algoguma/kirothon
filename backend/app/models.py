"""ORM models for the tables in spec section 5 (Backend)."""

from datetime import UTC, datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, LargeBinary, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


def utc_now() -> datetime:
    return datetime.now(UTC)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_user_id: Mapped[int] = mapped_column(BigInteger, unique=True)
    display_name: Mapped[str] = mapped_column(String(255))
    # Per-user Telegram app credentials (spec 3.2). Cleared on logout.
    api_id: Mapped[int | None]
    encrypted_api_hash: Mapped[bytes | None] = mapped_column(LargeBinary)
    encrypted_session: Mapped[bytes | None] = mapped_column(LargeBinary)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class LlmSettings(Base):
    __tablename__ = "llm_settings"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    encrypted_api_key: Mapped[bytes] = mapped_column(LargeBinary)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
