"""One live TelegramClient per logged-in user (spec 3.3) and the enabled-chat cache (spec 4)."""

import logging

from sqlalchemy import select
from telethon import TelegramClient
from telethon.sessions import StringSession

from app.crypto import decrypt
from app.db import SessionLocal
from app.errors import ApiError
from app.models import ChatSettings, User
from app.telegram.auto_reply import AutoReplier
from app.telegram.entities import display_name

logger = logging.getLogger(__name__)


class ClientManager:
    def __init__(self) -> None:
        self._clients: dict[int, TelegramClient] = {}
        # user_id -> {chat_id: current session_id}; avoids a DB lookup per message.
        self._enabled: dict[int, dict[int, int]] = {}
        self._auto = AutoReplier(self.session_for)

    async def start(self) -> None:
        """Reconnect every user with a saved session and load enabled chats."""
        async with SessionLocal() as db:
            users = (
                await db.scalars(select(User).where(User.encrypted_session.is_not(None)))
            ).all()
            rows = (await db.scalars(select(ChatSettings).where(ChatSettings.enabled))).all()
        for row in rows:
            if row.current_session_id is not None:
                self._enabled.setdefault(row.user_id, {})[row.chat_id] = row.current_session_id
        for user in users:
            assert user.api_id and user.encrypted_api_hash and user.encrypted_session
            await self.add_user(
                user.id,
                user.api_id,
                decrypt(user.encrypted_api_hash),
                decrypt(user.encrypted_session),
            )

    async def stop(self) -> None:
        for user_id in list(self._clients):
            await self.remove_user(user_id)

    async def add_user(self, user_id: int, api_id: int, api_hash: str, session: str) -> None:
        if user_id in self._clients:
            await self.remove_user(user_id)
        client = TelegramClient(StringSession(session), api_id, api_hash)
        try:
            await client.connect()
            if not await client.is_user_authorized():
                logger.warning("Saved session for user %s is no longer authorized", user_id)
                await client.disconnect()
                return
            me = await client.get_me()
        except Exception as exc:
            # Never log the exception text; it may echo connection details.
            logger.warning("Could not connect client for user %s: %s", user_id, type(exc).__name__)
            await client.disconnect()
            return
        self._auto.attach(user_id, client, display_name(me))
        self._clients[user_id] = client
        logger.info("Telegram client connected for user %s", user_id)

    async def remove_user(self, user_id: int) -> None:
        self._auto.cancel_user(user_id)
        self._enabled.pop(user_id, None)
        client = self._clients.pop(user_id, None)
        if client is not None:
            await client.disconnect()

    def get(self, user_id: int) -> TelegramClient:
        client = self._clients.get(user_id)
        if client is None or not client.is_connected():
            raise ApiError(401, "UNAUTHORIZED", "텔레그램 연결이 끊겼습니다. 다시 로그인해 주세요.")
        return client

    def enable(self, user_id: int, chat_id: int, session_id: int) -> None:
        self._enabled.setdefault(user_id, {})[chat_id] = session_id

    def disable(self, user_id: int, chat_id: int) -> None:
        self._enabled.get(user_id, {}).pop(chat_id, None)
        self._auto.cancel(user_id, chat_id)

    def session_for(self, user_id: int, chat_id: int) -> int | None:
        return self._enabled.get(user_id, {}).get(chat_id)


client_manager = ClientManager()
