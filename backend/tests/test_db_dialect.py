import pytest
from sqlalchemy import Column, Integer, String, select

from halite.db import Base, build_engine, build_sessionmaker
from halite.db_dialect import lower_eq


class _Thing(Base):
    __tablename__ = "_thing_for_test"
    id = Column(Integer, primary_key=True)
    name_lower = Column(String, nullable=False, index=True, unique=True)


@pytest.mark.asyncio
async def test_lower_eq_matches_case_insensitively():
    engine = build_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    sm = build_sessionmaker(engine)
    async with sm() as s:
        s.add(_Thing(name_lower="alice"))
        await s.commit()
    async with sm() as s:
        stmt = select(_Thing).where(lower_eq(_Thing.name_lower, "ALICE"))
        result = await s.execute(stmt)
        assert result.scalar_one().name_lower == "alice"
    await engine.dispose()
