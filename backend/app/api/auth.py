"""Web login API (spec 7.1): send-code, sign-in, password, logout."""

import re

from fastapi import APIRouter, Response
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import SESSION_COOKIE, SESSION_MAX_AGE_SEC, CurrentUser, DbSession
from app.api.me import MeResponse, build_me
from app.crypto import decrypt, encrypt
from app.models import AutoReplySession, ChatSettings, User, utc_now
from app.telegram.login import LoginResult, log_out_session, login_manager
from app.telegram.manager import client_manager

router = APIRouter(prefix="/api/auth", tags=["auth"])

_PHONE_RE = re.compile(r"^\+\d{7,15}$")


class SendCodeRequest(BaseModel):
    api_id: int = Field(gt=0)
    api_hash: str = Field(pattern=r"^[0-9a-fA-F]{32}$")
    phone: str

    @field_validator("phone")
    @classmethod
    def normalize_phone(cls, value: str) -> str:
        phone = re.sub(r"[\s\-()]", "", value)
        if not _PHONE_RE.fullmatch(phone):
            raise ValueError("phone must be in international format, e.g. +821012345678")
        return phone


class SendCodeResponse(BaseModel):
    login_id: str


class SignInRequest(BaseModel):
    login_id: str = Field(min_length=1)
    code: str = Field(pattern=r"^\d{4,8}$")


class PasswordRequest(BaseModel):
    login_id: str = Field(min_length=1)
    password: str = Field(min_length=1)


@router.post("/send-code")
async def send_code(body: SendCodeRequest) -> SendCodeResponse:
    login_id = await login_manager.send_code(body.api_id, body.api_hash.lower(), body.phone)
    return SendCodeResponse(login_id=login_id)


@router.post("/sign-in")
async def sign_in(body: SignInRequest, response: Response, db: DbSession) -> MeResponse:
    result = await login_manager.sign_in(body.login_id, body.code)
    return await _complete_login(db, response, result)


@router.post("/password")
async def password(body: PasswordRequest, response: Response, db: DbSession) -> MeResponse:
    result = await login_manager.check_password(body.login_id, body.password)
    return await _complete_login(db, response, result)


@router.post("/logout", status_code=204)
async def logout(user: CurrentUser, db: DbSession, response: Response) -> None:
    await client_manager.remove_user(user.id)
    # Auto reply cannot run without a session, so close any open auto-reply sessions.
    now = utc_now()
    await db.execute(
        update(AutoReplySession)
        .where(AutoReplySession.user_id == user.id, AutoReplySession.ended_at.is_(None))
        .values(ended_at=now)
    )
    await db.execute(
        update(ChatSettings)
        .where(ChatSettings.user_id == user.id, ChatSettings.enabled)
        .values(enabled=False, current_session_id=None)
    )
    if user.api_id and user.encrypted_api_hash and user.encrypted_session:
        await log_out_session(
            user.api_id, decrypt(user.encrypted_api_hash), decrypt(user.encrypted_session)
        )
    user.api_id = None
    user.encrypted_api_hash = None
    user.encrypted_session = None
    await db.commit()
    response.delete_cookie(SESSION_COOKIE, path="/")


async def _complete_login(db: AsyncSession, response: Response, result: LoginResult) -> MeResponse:
    user = await db.scalar(select(User).where(User.telegram_user_id == result.telegram_user_id))
    if user is None:
        user = User(telegram_user_id=result.telegram_user_id, display_name=result.display_name)
        db.add(user)
    user.display_name = result.display_name
    user.api_id = result.api_id
    user.encrypted_api_hash = encrypt(result.api_hash)
    user.encrypted_session = encrypt(result.session)
    await db.commit()
    await client_manager.add_user(user.id, result.api_id, result.api_hash, result.session)

    # Cookie value is a Fernet token of the user id: tamper-proof and expires with ttl.
    response.set_cookie(
        SESSION_COOKIE,
        encrypt(str(user.id)).decode(),
        max_age=SESSION_MAX_AGE_SEC,
        httponly=True,
        samesite="lax",
        path="/",
    )
    return build_me(user)
