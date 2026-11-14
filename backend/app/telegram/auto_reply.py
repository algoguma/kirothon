"""Debounced auto reply and message logging (spec 6.2)."""

import asyncio
import logging
from collections.abc import Callable

from sqlalchemy import update
from sqlalchemy.dialects.sqlite import insert
from telethon import TelegramClient, events
from telethon.tl.custom import Message as TgMessage

from app.ai import ChatMessage, LLMError, generate_reply
from app.db import SessionLocal
from app.models import ChatSettings, Message
from app.telegram.entities import display_name, is_private_user, message_text
from app.timeutil import as_utc

logger = logging.getLogger(__name__)

HISTORY_LIMIT = 20  # spec 3.4

Key = tuple[int, int]  # (user_id, chat_id)


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

    def cancel_user(self, user_id: int) -> None:
        for key in [k for k in self._pending if k[0] == user_id]:
            self.cancel(*key)
        self._me.pop(user_id, None)

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
                history = await self._history(user_id, client, chat_id)
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
        self, user_id: int, client: TelegramClient, chat_id: int
    ) -> list[ChatMessage]:
        msgs = await client.get_messages(chat_id, limit=HISTORY_LIMIT)
        entity = await client.get_entity(chat_id)
        partner, me = display_name(entity), self._me.get(user_id, "나")
        return [
            ChatMessage(
                sender_name=me if m.out else partner,
                text=message_text(m),
                date=as_utc(m.date),
                is_outgoing=bool(m.out),
            )
            for m in reversed(msgs)  # oldest first
        ]

    @staticmethod
    async def _set_last_error(key: Key, error: str | None) -> None:
        async with SessionLocal() as db:
            await db.execute(
                update(ChatSettings)
                .where(ChatSettings.user_id == key[0], ChatSettings.chat_id == key[1])
                .values(last_error=error)
            )
            await db.commit()
