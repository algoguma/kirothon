"""Auto-reply sessions, message preview and export (spec 6.4, 7.4)."""

import csv
import io
import json
import logging
from datetime import datetime
from typing import Literal
from urllib.parse import quote

from fastapi import APIRouter, Response
from pydantic import BaseModel
from sqlalchemy import case, func, select

from app.api.deps import CurrentUser, DbSession
from app.errors import ApiError
from app.models import AutoReplySession, ChatSettings, Message, User, utc_now
from app.telegram.entities import message_text
from app.telegram.manager import client_manager
from app.timeutil import KST, as_utc, iso_utc

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["sessions"])

BACKFILL_LIMIT = 5000


class SessionOut(BaseModel):
    id: int
    started_at: str
    ended_at: str | None
    message_count: int
    auto_reply_count: int


class MessageOut(BaseModel):
    message_id: int
    sender_name: str
    text: str
    date: str
    is_outgoing: bool
    is_auto_reply: bool


def _not_found() -> ApiError:
    return ApiError(404, "NOT_FOUND", "기록을 찾을 수 없습니다.")


@router.get("/chats/{chat_id}/sessions")
async def list_sessions(chat_id: int, user: CurrentUser, db: DbSession) -> list[SessionOut]:
    if await db.get(ChatSettings, (user.id, chat_id)) is None:
        raise _not_found()
    counts = (
        select(
            Message.session_id,
            func.count().label("total"),
            func.sum(case((Message.is_auto_reply, 1), else_=0)).label("auto"),
        )
        .where(Message.user_id == user.id, Message.chat_id == chat_id)
        .group_by(Message.session_id)
        .subquery()
    )
    rows = await db.execute(
        select(AutoReplySession, counts.c.total, counts.c.auto)
        .outerjoin(counts, counts.c.session_id == AutoReplySession.id)
        .where(AutoReplySession.user_id == user.id, AutoReplySession.chat_id == chat_id)
        .order_by(AutoReplySession.id.desc())
    )
    return [
        SessionOut(
            id=s.id,
            started_at=iso_utc(s.started_at) or "",
            ended_at=iso_utc(s.ended_at),
            message_count=total or 0,
            auto_reply_count=auto or 0,
        )
        for s, total, auto in rows
    ]


async def _session_messages(
    db: DbSession, user: User, session_id: int
) -> tuple[AutoReplySession, str, list[MessageOut]]:
    session = await db.scalar(
        select(AutoReplySession).where(
            AutoReplySession.id == session_id, AutoReplySession.user_id == user.id
        )
    )
    if session is None:
        raise _not_found()
    settings = await db.get(ChatSettings, (user.id, session.chat_id))
    partner = settings.chat_name if settings else str(session.chat_id)

    stored = await db.scalars(
        select(Message)
        .where(Message.user_id == user.id, Message.session_id == session.id)
        .order_by(Message.date, Message.message_id)
    )
    by_id = {
        m.message_id: MessageOut(
            message_id=m.message_id,
            sender_name=m.sender_name,
            text=m.text,
            date=iso_utc(m.date) or "",
            is_outgoing=m.is_outgoing,
            is_auto_reply=m.is_auto_reply,
        )
        for m in stored
    }
    await _backfill(user, session, partner, by_id)
    return session, partner, sorted(by_id.values(), key=lambda m: (m.date, m.message_id))


async def _backfill(
    user: User, session: AutoReplySession, partner: str, by_id: dict[int, MessageOut]
) -> None:
    """Fill gaps from Telegram for time the backend was down (spec 6.4). Best effort."""
    client = client_manager.find(user.id)
    if client is None:
        return
    start = as_utc(session.started_at)
    end = as_utc(session.ended_at) if session.ended_at else utc_now()
    try:
        async for msg in client.iter_messages(
            session.chat_id, offset_date=start, reverse=True, limit=BACKFILL_LIMIT
        ):
            if as_utc(msg.date) > end:
                break
            if msg.id in by_id:
                continue
            by_id[msg.id] = MessageOut(
                message_id=msg.id,
                sender_name=user.display_name if msg.out else partner,
                text=message_text(msg),
                date=iso_utc(msg.date) or "",
                is_outgoing=bool(msg.out),
                is_auto_reply=False,  # unknown for messages we did not log
            )
    except Exception as exc:
        logger.warning("Backfill failed for session %s: %s", session.id, type(exc).__name__)


@router.get("/sessions/{session_id}/messages")
async def session_messages(session_id: int, user: CurrentUser, db: DbSession) -> list[MessageOut]:
    _, _, messages = await _session_messages(db, user, session_id)
    return messages


def _kst(iso: str) -> datetime:
    return datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone(KST)


def _speaker(m: MessageOut) -> str:
    if m.is_auto_reply:
        return "나 (AI)"
    return "나" if m.is_outgoing else m.sender_name


@router.get("/sessions/{session_id}/export")
async def export_session(
    session_id: int,
    user: CurrentUser,
    db: DbSession,
    format: Literal["json", "csv", "txt"] = "json",
) -> Response:
    session, partner, messages = await _session_messages(db, user, session_id)

    if format == "json":
        data = [m.model_dump() | {"date": _kst(m.date).isoformat()} for m in messages]
        body = json.dumps(data, ensure_ascii=False, indent=2).encode()
        media_type = "application/json"
    elif format == "csv":
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(["date", "sender_name", "text", "is_auto_reply"])
        for m in messages:
            date = _kst(m.date).strftime("%Y-%m-%d %H:%M:%S")
            writer.writerow([date, _speaker(m), m.text, m.is_auto_reply])
        body = buf.getvalue().encode("utf-8-sig")  # BOM so Excel reads Korean correctly
        media_type = "text/csv"
    else:
        lines = [f"[{_kst(m.date):%Y-%m-%d %H:%M}] {_speaker(m)}: {m.text}" for m in messages]
        body = ("\n".join(lines) + "\n").encode()
        media_type = "text/plain"

    start = as_utc(session.started_at).astimezone(KST)
    end = as_utc(session.ended_at or utc_now()).astimezone(KST)
    filename = f"{partner}_{start:%Y-%m-%d}_{start:%H%M}-{end:%H%M}.{format}"
    # Header values must be latin-1: ASCII fallback plus RFC 5987 UTF-8 name.
    disposition = (
        f'attachment; filename="session-{session.id}.{format}"; '
        f"filename*=UTF-8''{quote(filename)}"
    )
    return Response(
        body,
        media_type=f"{media_type}; charset=utf-8",
        headers={"Content-Disposition": disposition},
    )
