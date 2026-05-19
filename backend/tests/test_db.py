import pytest
from sqlalchemy import text

from halite.db import Base, build_engine, build_sessionmaker


@pytest.mark.asyncio
async def test_engine_executes_simple_query():
    engine = build_engine("sqlite+aiosqlite:///:memory:")
    async with engine.connect() as conn:
        result = await conn.execute(text("SELECT 1"))
        row = result.first()
    assert row[0] == 1
    await engine.dispose()


@pytest.mark.asyncio
async def test_sessionmaker_yields_async_session():
    engine = build_engine("sqlite+aiosqlite:///:memory:")
    sessionmaker = build_sessionmaker(engine)
    async with sessionmaker() as session:
        result = await session.execute(text("SELECT 1"))
        assert result.scalar() == 1
    await engine.dispose()


def test_base_is_declarative_base():
    assert hasattr(Base, "metadata")
