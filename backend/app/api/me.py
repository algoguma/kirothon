"""GET /api/me (spec 7.2)."""

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, DbSession
from app.models import LlmSettings, User

router = APIRouter(prefix="/api/me", tags=["me"])


class UserOut(BaseModel):
    id: int
    display_name: str


class MeResponse(BaseModel):
    user: UserOut
    llm_configured: bool


async def build_me(db: AsyncSession, user: User) -> MeResponse:
    llm_user_id = await db.scalar(select(LlmSettings.user_id).where(LlmSettings.user_id == user.id))
    return MeResponse(
        user=UserOut(id=user.id, display_name=user.display_name),
        llm_configured=llm_user_id is not None,
    )


@router.get("")
async def me(user: CurrentUser, db: DbSession) -> MeResponse:
    return await build_me(db, user)
