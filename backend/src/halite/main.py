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

    from halite.logging_setup import setup_logging
    setup_logging(level=settings.log_level, fmt=settings.log_format)

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        from halite import db as db_module
        from halite.bootstrap import bootstrap_admin
        from halite.rbac.seed import seed_builtin_roles

        init_engine(settings.database_url)
        assert db_module._sessionmaker is not None
        async with db_module._sessionmaker() as s:
            await seed_builtin_roles(s)
            await s.commit()
            await bootstrap_admin(s, settings)
            await s.commit()
        try:
            yield
        finally:
            await dispose_engine()

    app = FastAPI(title="Halite", version="0.1.0", lifespan=lifespan)
    app.state.settings = settings
    app.state.cookie_codec = codec

    from halite.audit.routes import router as audit_router
    from halite.auth.routes import router as auth_router
    app.include_router(health_router)
    app.include_router(auth_router)
    app.include_router(audit_router)
    return app


# Module-level `app` is intentionally NOT created here — Settings() reads env
# vars and would fail at import time when env isn't set (e.g. during tests).
# Uvicorn launches via the factory pattern: `uvicorn halite.main:create_app --factory`.
