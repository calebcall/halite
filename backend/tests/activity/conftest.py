"""Activity-specific fixtures.

Uses create_all so the round-trip test works before the alembic migration for
activity_events exists (migration is Task 2).
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from halite.db import Base

# Import models so Base.metadata knows about activity_events and jobs_index.
import halite.activity.models  # noqa: F401
import halite.jobs.index_model  # noqa: F401


async def _make_engine() -> AsyncEngine:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    return engine


@pytest_asyncio.fixture()
async def session() -> AsyncIterator[AsyncSession]:
    engine = await _make_engine()
    sm = async_sessionmaker(engine, expire_on_commit=False)
    async with sm() as s:
        yield s
    await engine.dispose()


@pytest_asyncio.fixture()
async def db_sessionmaker() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine = await _make_engine()
    sm = async_sessionmaker(engine, expire_on_commit=False)
    yield sm
    await engine.dispose()
