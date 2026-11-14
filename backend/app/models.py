"""ORM models for the tables in spec section 5 (Backend)."""

from datetime import UTC, datetime

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Index,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
)
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


class ChatSettings(Base):
    __tablename__ = "chat_settings"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    chat_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    chat_name: Mapped[str] = mapped_column(String(255), default="")
    enabled: Mapped[bool] = mapped_column(default=False)
    reply_delay_sec: Mapped[int] = mapped_column(default=30)
    ai_instructions: Mapped[str] = mapped_column(Text, default="")
    fallback_text: Mapped[str | None] = mapped_column(Text)
    current_session_id: Mapped[int | None]
    last_error: Mapped[str | None] = mapped_column(Text)


class AutoReplySession(Base):
    __tablename__ = "auto_reply_sessions"
    __table_args__ = (Index("ix_sessions_user_chat", "user_id", "chat_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    chat_id: Mapped[int] = mapped_column(BigInteger)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Message(Base):
    __tablename__ = "messages"
    __table_args__ = (UniqueConstraint("user_id", "chat_id", "message_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("auto_reply_sessions.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    chat_id: Mapped[int] = mapped_column(BigInteger)
    message_id: Mapped[int] = mapped_column(BigInteger)
    sender_name: Mapped[str] = mapped_column(String(255))
    text: Mapped[str] = mapped_column(Text)
    date: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    is_outgoing: Mapped[bool]
    is_auto_reply: Mapped[bool] = mapped_column(default=False)
