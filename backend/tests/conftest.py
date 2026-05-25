"""
Shared fixtures.

DB-touching tests run against two backends:
  * SQLite in-memory/file (default; fast)
  * Postgres via testcontainers (enabled by HALITE_TEST_PG=1)

CI runs both legs. Locally, you can run only SQLite for speed.

Note: alembic's env.py uses asyncio.run() internally, so `command.upgrade`
must run from a SYNC context — fixtures that drive migrations are therefore
sync (pytest.fixture, not pytest_asyncio.fixture). Async session fixtures
are layered on top after migrations have completed.
"""

from __future__ import annotations

import os
import time
from collections.abc import AsyncIterator, Callable, Iterator
from dataclasses import dataclass, field
from typing import Any

import httpx
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import halite.db as db_module
from alembic import command
from alembic.config import Config


def _backends() -> list[str]:
    backends = ["sqlite"]
    if os.getenv("HALITE_TEST_PG") == "1":
        backends.append("postgres")
    return backends


@pytest.fixture(scope="session", params=_backends())
def db_backend(request) -> str:
    return request.param


@pytest.fixture()
def db_url(db_backend, tmp_path_factory) -> Iterator[str]:
    if db_backend == "sqlite":
        path = tmp_path_factory.mktemp("db") / "test.db"
        yield f"sqlite+aiosqlite:///{path}"
    else:
        from testcontainers.postgres import PostgresContainer

        with PostgresContainer("postgres:16") as pg:
            sync_url = pg.get_connection_url()
            yield sync_url.replace("postgresql+psycopg2", "postgresql+asyncpg")


@pytest.fixture()
def migrated_db_url(db_url, monkeypatch) -> str:
    monkeypatch.setenv("DATABASE_URL", db_url)
    monkeypatch.setenv("COOKIE_SECRET", "x" * 64)
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", db_url)
    command.upgrade(cfg, "head")
    return db_url


@pytest_asyncio.fixture()
async def session(migrated_db_url) -> AsyncIterator[AsyncSession]:
    engine = create_async_engine(migrated_db_url)
    sm = async_sessionmaker(engine, expire_on_commit=False)
    async with sm() as s:
        yield s
    await engine.dispose()


@pytest_asyncio.fixture()
async def app_db(migrated_db_url) -> AsyncIterator[str]:
    """Initialise the app's process-global engine pointing at the migrated DB."""
    db_module.init_engine(migrated_db_url)
    try:
        yield migrated_db_url
    finally:
        await db_module.dispose_engine()


# ---- Fake salt-api fixture ----
#
# httpx.MockTransport with stateful routing. Tests configure the fixture's
# responses via attribute assignment:
#
#   fake_salt_api.login_response = {"return": [{"token": "abc", "expire": time.time() + 3600, ...}]}
#   fake_salt_api.run_handler = lambda payload: {"return": [...]}
#
# The fixture also exposes:
#   fake_salt_api.calls  -- list of (path, payload) tuples
#   fake_salt_api.transport  -- the httpx.MockTransport instance for direct use
#
# The fixture does NOT wire itself into the SaltAPIClient — tests should
# pass `transport=fake_salt_api.transport` when constructing the client.


@dataclass
class FakeSaltAPI:
    login_response: dict[str, Any] = field(
        default_factory=lambda: {
            "return": [
                {
                    "token": "fake-token-abc",
                    "expire": time.time() + 3600,
                    "start": time.time(),
                    "user": "halite-service",
                    "eauth": "pam",
                    "perms": [".*"],
                }
            ]
        }
    )
    run_handler: Callable[[dict[str, Any]], dict[str, Any]] | None = None
    calls: list[tuple[str, dict[str, Any] | None]] = field(default_factory=list)
    login_status: int = 200
    run_status: int = 200

    @property
    def transport(self) -> httpx.MockTransport:
        def handler(request: httpx.Request) -> httpx.Response:
            path = request.url.path
            try:
                body = request.read()
                payload = httpx.Response(0, content=body).json() if body else None
            except Exception:
                payload = None
            self.calls.append((path, payload))

            if path == "/login":
                if self.login_status >= 400:
                    return httpx.Response(self.login_status, json={"detail": "login rejected"})
                return httpx.Response(self.login_status, json=self.login_response)

            # The real client POSTs lowstates to the session-aware root endpoint
            # (`/`) with X-Auth-Token. We keep `/run` accepted here too for
            # backwards compatibility with any direct callers.
            if path in ("/", "/run"):
                if self.run_status >= 400:
                    return httpx.Response(self.run_status, json={"detail": "run failed"})
                if self.run_handler is None:
                    return httpx.Response(200, json={"return": [None]})
                # salt-api accepts a list of payloads; we look at the first.
                payload_one = (
                    payload[0] if isinstance(payload, list) and payload else (payload or {})
                )
                return httpx.Response(200, json=self.run_handler(payload_one))

            return httpx.Response(404, json={"detail": f"unknown path {path}"})

        return httpx.MockTransport(handler)


@pytest.fixture()
def fake_salt_api() -> FakeSaltAPI:
    return FakeSaltAPI()
