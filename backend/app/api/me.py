"""GET /api/me (spec 7.2)."""

from fastapi import APIRouter
from pydantic import BaseModel

from app.api.deps import CurrentUser
from app.models import User

router = APIRouter(prefix="/api/me", tags=["me"])


class UserOut(BaseModel):
    id: int
    display_name: str


class MeResponse(BaseModel):
    user: UserOut


def build_me(user: User) -> MeResponse:
    return MeResponse(user=UserOut(id=user.id, display_name=user.display_name))


@router.get("")
async def me(user: CurrentUser) -> MeResponse:
    return build_me(user)
