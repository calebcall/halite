from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from halite.auth.cookies import CookieCodec
from halite.config import Settings, get_settings
from halite.db import dispose_engine, init_engine
from halite.health import router as health_router

logger = logging.getLogger(__name__)


def create_app(
    settings: Settings | None = None,
    codec: CookieCodec | None = None,
) -> FastAPI:
    settings = settings or get_settings()
    codec = codec or CookieCodec(settings.cookie_secret)

    from halite.logging_setup import setup_logging
    setup_logging(level=settings.log_level, fmt=settings.log_format)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        from halite import db as db_module
        from halite.bootstrap import bootstrap_admin
        from halite.rbac.seed import seed_builtin_roles
        from halite.salt.client import SaltAPIClient

        init_engine(settings.database_url)
        assert db_module._sessionmaker is not None
        async with db_module._sessionmaker() as s:
            await seed_builtin_roles(s)
            await s.commit()
            await bootstrap_admin(s, settings)
            await s.commit()

        # Optional salt-api client. Only instantiate when fully configured.
        salt_client: SaltAPIClient | None = None
        if (
            settings.salt_api_url
            and settings.salt_api_username
            and settings.salt_api_password
        ):
            salt_client = SaltAPIClient(
                base_url=settings.salt_api_url,
                username=settings.salt_api_username,
                password=settings.salt_api_password,
                eauth=settings.salt_api_eauth,
                verify=_parse_verify(settings.salt_api_verify),
            )
        app.state.salt_client = salt_client

        # Inventory background refresh — only when salt-api is configured AND
        # the operator opted in via INVENTORY_REFRESH_MINUTES > 0. Otherwise
        # refreshes are entirely on-demand via the UI.
        inventory_task: asyncio.Task[None] | None = None
        if salt_client is not None and settings.inventory_refresh_minutes > 0:
            from halite.inventory.scheduler import run_inventory_scheduler
            assert db_module._sessionmaker is not None
            inventory_task = asyncio.create_task(
                run_inventory_scheduler(
                    sessionmaker=db_module._sessionmaker,
                    client=salt_client,
                    interval_minutes=settings.inventory_refresh_minutes,
                    initial_delay_s=settings.inventory_refresh_initial_delay_s,
                ),
                name="inventory-scheduler",
            )

        try:
            yield
        finally:
            if inventory_task is not None:
                inventory_task.cancel()
                try:
                    await inventory_task
                except (asyncio.CancelledError, Exception) as exc:
                    # Swallow cancellation; log anything else so a buggy
                    # scheduler doesn't take down the shutdown path silently.
                    if not isinstance(exc, asyncio.CancelledError):
                        logger.exception("inventory scheduler exited with error")
            if salt_client is not None:
                await salt_client.aclose()
            await dispose_engine()

    app = FastAPI(title="Halite", version="0.1.0", lifespan=lifespan)
    app.state.settings = settings
    app.state.cookie_codec = codec

    from halite.audit.routes import router as audit_router
    from halite.auth.routes import router as auth_router
    from halite.inventory.routes import router as inventory_router
    from halite.jobs.routes import router as jobs_router
    from halite.keys.routes import router as keys_router
    from halite.minions.routes import router as minions_router
    from halite.rbac.routes import router as rbac_router
    from halite.run.routes import router as run_router
    from halite.salt_docs.routes import router as salt_docs_router
    from halite.users.routes import router as users_router
    app.include_router(health_router)
    app.include_router(auth_router)
    app.include_router(audit_router)
    app.include_router(inventory_router)
    app.include_router(jobs_router)
    app.include_router(keys_router)
    app.include_router(minions_router)
    app.include_router(rbac_router)
    app.include_router(run_router)
    app.include_router(salt_docs_router)
    app.include_router(users_router)

    if settings.static_dir:
        from pathlib import Path

        from fastapi.responses import FileResponse
        from fastapi.staticfiles import StaticFiles

        static_path = Path(settings.static_dir)
        if static_path.is_dir():
            assets_dir = static_path / "assets"
            if assets_dir.is_dir():
                app.mount(
                    "/assets",
                    StaticFiles(directory=assets_dir),
                    name="assets",
                )

            static_root = static_path.resolve()

            @app.get("/{full_path:path}", include_in_schema=False)
            async def serve_spa(full_path: str):
                # Serve real files from the static root first (favicon.svg,
                # apple-touch-icon.png, robots.txt, etc.) — otherwise iOS Safari
                # gets index.html when asking for the touch icon and falls back
                # to a generated letter icon. Unknown paths still return
                # index.html so the SPA can route client-side.
                if full_path:
                    candidate = (static_path / full_path).resolve()
                    if (
                        candidate.is_file()
                        and candidate.is_relative_to(static_root)
                    ):
                        return FileResponse(candidate)
                return FileResponse(static_path / "index.html")

    return app


def _parse_verify(value: str) -> bool | str:
    """SALT_API_VERIFY can be 'true', 'false', or a path to a CA bundle."""
    if value.lower() == "true":
        return True
    if value.lower() == "false":
        return False
    return value


# Module-level `app` is intentionally NOT created here — Settings() reads env
# vars and would fail at import time when env isn't set (e.g. during tests).
# Uvicorn launches via the factory pattern: `uvicorn halite.main:create_app --factory`.
