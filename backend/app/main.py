from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.db import init_db
from app.errors import register_error_handlers


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    await init_db()
    # TODO(Backend): start ClientManager and reconnect saved sessions
    yield
    # TODO(Backend): disconnect Telethon clients


app = FastAPI(title="kirothon", lifespan=lifespan)
register_error_handlers(app)


@app.get("/api/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
