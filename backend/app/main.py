from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.auth import router as auth_router
from app.api.chats import router as chats_router
from app.api.me import router as me_router
from app.crypto import check_key
from app.db import init_db
from app.errors import register_error_handlers
from app.telegram.login import login_manager
from app.telegram.manager import client_manager


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    check_key()  # fail at startup, not after a user has finished logging in
    await init_db()
    await client_manager.start()
    yield
    await login_manager.close_all()
    await client_manager.stop()


app = FastAPI(title="kirothon", lifespan=lifespan)
register_error_handlers(app)
app.include_router(auth_router)
app.include_router(me_router)
app.include_router(chats_router)


@app.get("/api/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
