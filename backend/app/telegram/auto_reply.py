"""Debounced auto reply and message logging (spec 6.2)."""

import asyncio
import logging
import shutil
from collections.abc import Callable
from pathlib import Path

from sqlalchemy import update
from sqlalchemy.dialects.sqlite import insert
from telethon import TelegramClient, events
from telethon.tl.custom import Message as TgMessage

from app.ai import (
    ChatMessage,
    LLMError,
    analyze_chat,
    generate_persona_reply,
    generate_reply,
    persona_ready,
)
from app.config import get_settings
from app.db import SessionLocal
from app.models import ChatSettings, Message
from app.telegram.entities import display_name, is_private_user, message_text
from app.timeutil import as_utc

logger = logging.getLogger(__name__)

REPLY_HISTORY_LIMIT = 160  # persona prompt uses the last 150 + the new messages
ANALYSIS_HISTORY_LIMIT = 1000  # style/memory analysis input on ON

Key = tuple[int, int]  # (user_id, chat_id)


def work_dir(user_id: int, chat_id: int) -> Path:
    """Chat history JSON + style.md/memory.md for one enabled chat. Deleted on OFF."""
    return Path(get_settings().data_dir) / str(user_id) / str(chat_id)


async def save_message(
    user_id: int,
    chat_id: int,
    session_id: int,
    msg: TgMessage,
    sender_name: str,
    is_auto_reply: bool,
) -> None:
    stmt = insert(Message).values(
        session_id=session_id,
        user_id=user_id,
        chat_id=chat_id,
        message_id=msg.id,
        sender_name=sender_name,
        text=message_text(msg),
        date=as_utc(msg.date),
        is_outgoing=bool(msg.out),
        is_auto_reply=is_auto_reply,
    )
    cols = [Message.user_id, Message.chat_id, Message.message_id]
    if is_auto_reply:
        # The outgoing event may have stored it first; mark it as an auto reply.
        stmt = stmt.on_conflict_do_update(index_elements=cols, set_={"is_auto_reply": True})
    else:
        stmt = stmt.on_conflict_do_nothing(index_elements=cols)
    async with SessionLocal() as db:
        await db.execute(stmt)
        await db.commit()


class AutoReplier:
    def __init__(self, session_for: Callable[[int, int], int | None]) -> None:
        self._session_for = session_for  # current session id if the chat is enabled
        self._pending: dict[Key, asyncio.Task[None]] = {}
        self._sending: dict[Key, str] = {}  # text being sent by auto reply right now
        self._sent_ids: set[tuple[int, int, int]] = set()
        self._me: dict[int, str] = {}  # user_id -> own display name
        self._analysis: dict[Key, asyncio.Task[None]] = {}

    def attach(self, user_id: int, client: TelegramClient, me_name: str) -> None:
        self._me[user_id] = me_name

        async def incoming(event: events.NewMessage.Event) -> None:
            await self._on_incoming(user_id, client, event)

        async def outgoing(event: events.NewMessage.Event) -> None:
            await self._on_outgoing(user_id, event)

        client.add_event_handler(incoming, events.NewMessage(incoming=True))
        client.add_event_handler(outgoing, events.NewMessage(outgoing=True))

    def cancel(self, user_id: int, chat_id: int) -> None:
        task = self._pending.pop((user_id, chat_id), None)
        if task is not None:
            task.cancel()

    def cancel_user(self, user_id: int, drop_data: bool = False) -> None:
        for key in [k for k in self._pending if k[0] == user_id]:
            self.cancel(*key)
        for key in [k for k in self._analysis if k[0] == user_id]:
            self._analysis.pop(key).cancel()
        self._me.pop(user_id, None)
        if drop_data:
            shutil.rmtree(Path(get_settings().data_dir) / str(user_id), ignore_errors=True)

    # --- style/memory analysis (runs on ON, deleted on OFF) ------------------------------

    def start_analysis(self, user_id: int, chat_id: int, client: TelegramClient) -> None:
        key = (user_id, chat_id)
        self.drop_analysis(user_id, chat_id)
        self._analysis[key] = asyncio.create_task(self._analyze(key, client))

    def ensure_analysis(self, user_id: int, chat_id: int, client: TelegramClient) -> None:
        """After a restart: analyze again if the previous run did not finish."""
        key = (user_id, chat_id)
        if key not in self._analysis and not persona_ready(str(work_dir(*key))):
            self.start_analysis(user_id, chat_id, client)

    def drop_analysis(self, user_id: int, chat_id: int) -> None:
        task = self._analysis.pop((user_id, chat_id), None)
        if task is not None:
            task.cancel()
        shutil.rmtree(work_dir(user_id, chat_id), ignore_errors=True)

    async def _analyze(self, key: Key, client: TelegramClient) -> None:
        user_id, chat_id = key
        session_id = self._session_for(*key)
        path = work_dir(*key)
        try:
            history, me, partner = await self._history(
                user_id, client, chat_id, ANALYSIS_HISTORY_LIMIT
            )
            logger.info("Analyzing %d messages for user %s", len(history), user_id)
            await analyze_chat(str(path), history, me, partner)
            if self._session_for(*key) != session_id:
                shutil.rmtree(path, ignore_errors=True)  # turned off while analyzing
            else:
                logger.info("Analysis ready for user %s", user_id)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            reason = str(exc) if isinstance(exc, LLMError) else type(exc).__name__
            logger.warning("Analysis failed for user %s: %s", user_id, reason)
            shutil.rmtree(path, ignore_errors=True)
            if self._session_for(*key) == session_id:
                await self._set_last_error(key, f"대화 분석 실패 (기본 방식으로 답장): {reason}")
        finally:
            if self._analysis.get(key) is asyncio.current_task():
                del self._analysis[key]

    async def _on_incoming(
        self, user_id: int, client: TelegramClient, event: events.NewMessage.Event
    ) -> None:
        if not event.is_private:
            return
        session_id = self._session_for(user_id, event.chat_id)
        if session_id is None:
            return
        sender = await event.get_sender()
        if not is_private_user(sender):
            return  # bots never get auto replies
        key = (user_id, event.chat_id)
        # Debounce: stop the running timer before any await so it cannot fire meanwhile.
        self.cancel(*key)
        await save_message(
            user_id, event.chat_id, session_id, event.message, display_name(sender), False
        )
        # Read settings here, not inside the task: cancelling a task mid-query leaks the
        # SQLite connection and locks the database.
        async with SessionLocal() as db:
            row = await db.get(ChatSettings, key)
        if row is None or not row.enabled or self._session_for(*key) is None:
            return
        self.cancel(*key)  # another message may have scheduled one during the awaits
        self._pending[key] = asyncio.create_task(self._reply_after_delay(key, client, row))

    async def _on_outgoing(self, user_id: int, event: events.NewMessage.Event) -> None:
        if not event.is_private:
            return
        key = (user_id, event.chat_id)
        session_id = self._session_for(*key)
        if session_id is None:
            return
        msg = event.message
        sent_key = (user_id, event.chat_id, msg.id)
        if sent_key in self._sent_ids:
            self._sent_ids.discard(sent_key)
            return
        if self._sending.get(key) == msg.message:
            return  # echo of the auto reply that is still being sent
        # The user answered personally: drop the pending AI reply (before any await).
        self.cancel(*key)
        await save_message(
            user_id, event.chat_id, session_id, msg, self._me.get(user_id, "나"), False
        )

    async def _reply_after_delay(self, key: Key, client: TelegramClient, row: ChatSettings) -> None:
        """No DB access before the task leaves _pending; until then it can be cancelled."""
        user_id, chat_id = key
        try:
            await asyncio.sleep(row.reply_delay_sec)

            error: str | None = None
            try:
                history, me, partner = await self._history(
                    user_id, client, chat_id, REPLY_HISTORY_LIMIT
                )
                path = str(work_dir(*key))
                if persona_ready(path):
                    result = await generate_persona_reply(
                        path, history, me, partner, row.ai_instructions
                    )
                    # Emergency / "owner must answer" notices show up in the chat list.
                    text, error = result.text, result.note
                else:
                    # Analysis still running or failed: spec 3.4 reply on the last 20 messages.
                    text = await generate_reply(history, row.ai_instructions)
            except LLMError as exc:
                error = str(exc)
                text = row.fallback_text or ""

            session_id = self._session_for(user_id, chat_id)
            if session_id is None:
                return  # turned off meanwhile
            if self._pending.get(key) is asyncio.current_task():
                # From here on a user reply or a new message must not cancel a half-sent reply.
                del self._pending[key]
            if text:
                self._sending[key] = text
                try:
                    sent = await client.send_message(chat_id, text)
                finally:
                    self._sending.pop(key, None)
                self._sent_ids.add((user_id, chat_id, sent.id))
                await save_message(
                    user_id, chat_id, session_id, sent, self._me.get(user_id, "나"), True
                )
            await self._set_last_error(key, error)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.warning("Auto reply failed for user %s: %s", user_id, type(exc).__name__)
            await self._set_last_error(key, "자동 답장을 보내지 못했습니다.")

    async def _history(
        self, user_id: int, client: TelegramClient, chat_id: int, limit: int
    ) -> tuple[list[ChatMessage], str, str]:
        """Recent chat from Telegram (oldest first), my name, partner name."""
        msgs = await client.get_messages(chat_id, limit=limit)
        entity = await client.get_entity(chat_id)
        partner, me = display_name(entity), self._me.get(user_id, "나")
        history = [
            ChatMessage(
                sender_name=me if m.out else partner,
                text=message_text(m),
                date=as_utc(m.date),
                is_outgoing=bool(m.out),
            )
            for m in reversed(msgs)
        ]
        return history, me, partner

    @staticmethod
    async def _set_last_error(key: Key, error: str | None) -> None:
        async with SessionLocal() as db:
            await db.execute(
                update(ChatSettings)
                .where(ChatSettings.user_id == key[0], ChatSettings.chat_id == key[1])
                .values(last_error=error)
            )
            await db.commit()
