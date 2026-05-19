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
from collections.abc import AsyncIterator, Iterator

import pytest
import pytest_asyncio
from alembic import command
from alembic.config import Config
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import halite.db as db_module


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
