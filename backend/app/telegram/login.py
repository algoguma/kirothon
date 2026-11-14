"""In-progress web logins: send-code -> sign-in -> (2FA) password (spec 3.2, 7.1).

Each login keeps its own TelegramClient in memory until it succeeds or expires, because
sign_in must run on the same connection that requested the code.
"""

import logging
import math
import secrets
import time
from dataclasses import dataclass

from telethon import TelegramClient
from telethon.errors import (
    ApiIdInvalidError,
    FloodWaitError,
    PasswordHashInvalidError,
    PhoneCodeExpiredError,
    PhoneCodeInvalidError,
    PhoneNumberBannedError,
    PhoneNumberInvalidError,
    PhoneNumberUnoccupiedError,
    SessionPasswordNeededError,
)
from telethon.sessions import StringSession

from app.errors import ApiError

logger = logging.getLogger(__name__)

LOGIN_TTL_SEC = 600  # spec 7.1: keep a pending login for 10 minutes
SEND_CODE_INTERVAL_SEC = 60  # security rule: one code request per phone per minute


@dataclass
class PendingLogin:
    client: TelegramClient
    api_id: int
    api_hash: str
    phone: str
    phone_code_hash: str
    expires_at: float
    password_required: bool = False


@dataclass(frozen=True)
class LoginResult:
    telegram_user_id: int
    display_name: str
    api_id: int
    api_hash: str
    session: str  # StringSession; encrypt before storing, never log


def _flood_wait(seconds: int) -> ApiError:
    return ApiError(
        429,
        "FLOOD_WAIT",
        f"요청이 너무 많습니다. {seconds}초 후에 다시 시도해 주세요.",
        retry_after_sec=seconds,
    )


class LoginManager:
    def __init__(self) -> None:
        self._pending: dict[str, PendingLogin] = {}
        self._last_code_at: dict[str, float] = {}

    async def send_code(self, api_id: int, api_hash: str, phone: str) -> str:
        await self._purge_expired()

        last = self._last_code_at.get(phone)
        if last is not None:
            remaining = SEND_CODE_INTERVAL_SEC - (time.monotonic() - last)
            if remaining > 0:
                raise _flood_wait(math.ceil(remaining))

        client = TelegramClient(StringSession(), api_id, api_hash)
        sent_ok = False
        try:
            await client.connect()
            sent = await client.send_code_request(phone)
            sent_ok = True
        except ApiIdInvalidError as exc:
            raise ApiError(
                400, "INVALID_API_CREDENTIALS", "api_id 또는 api_hash가 올바르지 않습니다."
            ) from exc
        except PhoneNumberInvalidError as exc:
            raise ApiError(422, "VALIDATION_ERROR", "전화번호가 올바르지 않습니다.") from exc
        except PhoneNumberBannedError as exc:
            raise ApiError(
                422, "VALIDATION_ERROR", "텔레그램에서 사용이 제한된 번호입니다."
            ) from exc
        except FloodWaitError as exc:
            raise _flood_wait(exc.seconds) from exc
        finally:
            if not sent_ok:
                await client.disconnect()

        self._last_code_at[phone] = time.monotonic()
        login_id = secrets.token_urlsafe(24)
        self._pending[login_id] = PendingLogin(
            client=client,
            api_id=api_id,
            api_hash=api_hash,
            phone=phone,
            phone_code_hash=sent.phone_code_hash,
            expires_at=time.monotonic() + LOGIN_TTL_SEC,
        )
        return login_id

    async def sign_in(self, login_id: str, code: str) -> LoginResult:
        pending = await self._get(login_id)
        try:
            await pending.client.sign_in(
                pending.phone, code, phone_code_hash=pending.phone_code_hash
            )
        except SessionPasswordNeededError as exc:
            pending.password_required = True
            raise ApiError(
                401, "PASSWORD_REQUIRED", "2단계 인증 비밀번호를 입력해 주세요."
            ) from exc
        except PhoneCodeInvalidError as exc:
            raise ApiError(400, "INVALID_CODE", "인증 코드가 올바르지 않습니다.") from exc
        except PhoneCodeExpiredError as exc:
            raise ApiError(
                400, "INVALID_CODE", "인증 코드가 만료되었습니다. 코드를 다시 받아 주세요."
            ) from exc
        except PhoneNumberUnoccupiedError as exc:
            raise ApiError(422, "VALIDATION_ERROR", "텔레그램에 가입되지 않은 번호입니다.") from exc
        except FloodWaitError as exc:
            raise _flood_wait(exc.seconds) from exc
        return await self._finish(login_id, pending)

    async def check_password(self, login_id: str, password: str) -> LoginResult:
        pending = await self._get(login_id)
        if not pending.password_required:
            raise ApiError(422, "VALIDATION_ERROR", "인증 코드를 먼저 입력해 주세요.")
        try:
            await pending.client.sign_in(password=password)
        except PasswordHashInvalidError as exc:
            raise ApiError(400, "INVALID_PASSWORD", "비밀번호가 올바르지 않습니다.") from exc
        except FloodWaitError as exc:
            raise _flood_wait(exc.seconds) from exc
        return await self._finish(login_id, pending)

    async def close_all(self) -> None:
        pending, self._pending = list(self._pending.values()), {}
        for item in pending:
            await item.client.disconnect()

    async def _get(self, login_id: str) -> PendingLogin:
        await self._purge_expired()
        pending = self._pending.get(login_id)
        if pending is None:
            raise ApiError(
                404, "NOT_FOUND", "로그인 요청이 만료되었습니다. 처음부터 다시 시도해 주세요."
            )
        return pending

    async def _finish(self, login_id: str, pending: PendingLogin) -> LoginResult:
        me = await pending.client.get_me()
        session = pending.client.session.save()
        self._pending.pop(login_id, None)
        # The saved session stays valid after disconnecting; ClientManager reconnects with it.
        await pending.client.disconnect()

        name = " ".join(part for part in (me.first_name, me.last_name) if part)
        return LoginResult(
            telegram_user_id=me.id,
            display_name=name or me.username or str(me.id),
            api_id=pending.api_id,
            api_hash=pending.api_hash,
            session=session,
        )

    async def _purge_expired(self) -> None:
        now = time.monotonic()
        expired = [key for key, item in self._pending.items() if item.expires_at <= now]
        for key in expired:
            await self._pending.pop(key).client.disconnect()
        self._last_code_at = {
            phone: at
            for phone, at in self._last_code_at.items()
            if now - at < SEND_CODE_INTERVAL_SEC
        }


async def log_out_session(api_id: int, api_hash: str, session: str) -> None:
    """Terminate a saved session on Telegram's side (spec 7.1 logout).

    Best effort: if Telegram is unreachable the caller still deletes the local session.
    """
    client: TelegramClient | None = None
    try:
        client = TelegramClient(StringSession(session), api_id, api_hash)
        await client.connect()
        await client.log_out()
    except Exception as exc:
        logger.warning("Telegram log_out failed: %s", type(exc).__name__)
    finally:
        if client is not None:
            await client.disconnect()


login_manager = LoginManager()
