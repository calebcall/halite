from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from halite.auth.cookies import CookieCodec
from halite.config import Settings, get_settings
from halite.db import dispose_engine, init_engine
from halite.health import router as health_router


def create_app(
    settings: Settings | None = None,
    codec: CookieCodec | None = None,
) -> FastAPI:
    settings = settings or get_settings()
    codec = codec or CookieCodec(settings.cookie_secret)

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        init_engine(settings.database_url)
        try:
            yield
        finally:
            await dispose_engine()

    app = FastAPI(title="Halite", version="0.1.0", lifespan=lifespan)
    app.state.settings = settings
    app.state.cookie_codec = codec
    app.include_router(health_router)
    return app


app = create_app()
