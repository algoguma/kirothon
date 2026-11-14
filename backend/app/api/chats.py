"""1:1 chat list and auto-reply on/off (spec 6.1, 6.3, 7.3)."""

from datetime import datetime

from fastapi import APIRouter
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from telethon import TelegramClient
from telethon.tl.types import User as TgUser

from app.api.deps import CurrentUser, DbSession
from app.errors import ApiError
from app.models import AutoReplySession, ChatSettings, utc_now
from app.telegram.manager import client_manager
from app.timeutil import iso_utc

router = APIRouter(prefix="/api/chats", tags=["chats"])

DIALOG_LIMIT = 200


class ChatOut(BaseModel):
    chat_id: int
    name: str
    last_message_at: str | None
    enabled: bool
    reply_delay_sec: int
    ai_instructions: str
    fallback_text: str | None
    current_session_id: int | None
    last_error: str | None


class AutoReplyUpdate(BaseModel):
    enabled: bool | None = None
    reply_delay_sec: int | None = Field(default=None, ge=30, le=120)
    ai_instructions: str | None = Field(default=None, max_length=2000)
    fallback_text: str | None = Field(default=None, max_length=1000)


def is_private_user(entity: object) -> bool:
    # Spec scope: 1:1 chats only; no bots, no "Saved Messages".
    return isinstance(entity, TgUser) and not entity.bot and not entity.is_self


def display_name(entity: TgUser) -> str:
    name = " ".join(part for part in (entity.first_name, entity.last_name) if part)
    return name or entity.username or str(entity.id)


def _chat_out(
    chat_id: int, name: str, last_at: datetime | None, row: ChatSettings | None
) -> ChatOut:
    return ChatOut(
        chat_id=chat_id,
        name=name,
        last_message_at=iso_utc(last_at),
        enabled=row.enabled if row else False,
        reply_delay_sec=row.reply_delay_sec if row else 30,
        ai_instructions=row.ai_instructions if row else "",
        fallback_text=row.fallback_text if row else None,
        current_session_id=row.current_session_id if row else None,
        last_error=row.last_error if row else None,
    )


@router.get("")
async def list_chats(user: CurrentUser, db: DbSession, q: str | None = None) -> list[ChatOut]:
    client = client_manager.get(user.id)
    rows = {
        row.chat_id: row
        for row in await db.scalars(select(ChatSettings).where(ChatSettings.user_id == user.id))
    }
    needle = (q or "").strip().lower()
    result: list[ChatOut] = []
    # iter_dialogs yields the most recent conversations first.
    async for dialog in client.iter_dialogs(limit=DIALOG_LIMIT):
        if not is_private_user(dialog.entity):
            continue
        name = display_name(dialog.entity)
        row = rows.get(dialog.id)
        if row is not None and row.chat_name != name:
            row.chat_name = name
        if needle and needle not in name.lower():
            continue
        result.append(_chat_out(dialog.id, name, dialog.date, row))
    await db.commit()
    return result


async def _private_entity(client: TelegramClient, chat_id: int) -> TgUser:
    not_found = ApiError(404, "NOT_FOUND", "채팅방을 찾을 수 없습니다.")
    try:
        entity = await client.get_entity(chat_id)
    except ValueError:
        # Entity not in the session cache yet; dialogs load it.
        await client.get_dialogs(limit=DIALOG_LIMIT)
        try:
            entity = await client.get_entity(chat_id)
        except ValueError:
            raise not_found from None
    if not is_private_user(entity):
        raise not_found
    return entity


async def turn_on(db: AsyncSession, user_id: int, row: ChatSettings) -> None:
    session = AutoReplySession(user_id=user_id, chat_id=row.chat_id, started_at=utc_now())
    db.add(session)
    await db.flush()
    row.enabled = True
    row.current_session_id = session.id


async def turn_off(db: AsyncSession, row: ChatSettings) -> None:
    if row.current_session_id is not None:
        session = await db.get(AutoReplySession, row.current_session_id)
        if session is not None and session.ended_at is None:
            session.ended_at = utc_now()
    row.enabled = False
    row.current_session_id = None


@router.put("/{chat_id}/auto-reply")
async def update_auto_reply(
    chat_id: int, body: AutoReplyUpdate, user: CurrentUser, db: DbSession
) -> ChatOut:
    client = client_manager.get(user.id)
    entity = await _private_entity(client, chat_id)
    row = await db.get(ChatSettings, (user.id, chat_id))
    if row is None:
        row = ChatSettings(
            user_id=user.id, chat_id=chat_id, enabled=False, reply_delay_sec=30, ai_instructions=""
        )
        db.add(row)
    row.chat_name = display_name(entity)

    if body.reply_delay_sec is not None:
        row.reply_delay_sec = body.reply_delay_sec
    if body.ai_instructions is not None:
        row.ai_instructions = body.ai_instructions
    if "fallback_text" in body.model_fields_set:
        row.fallback_text = (body.fallback_text or "").strip() or None
    if body.enabled is True and not row.enabled:
        await turn_on(db, user.id, row)
    elif body.enabled is False and row.enabled:
        await turn_off(db, row)
    await db.commit()
    # Update the in-memory cache only after the DB change is committed.
    if row.enabled and row.current_session_id is not None:
        client_manager.enable(user.id, chat_id, row.current_session_id)
    else:
        client_manager.disable(user.id, chat_id)

    last = await client.get_messages(entity, limit=1)
    return _chat_out(chat_id, row.chat_name, last[0].date if last else None, row)
