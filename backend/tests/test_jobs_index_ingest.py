from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select

from halite.jobs.index_model import JobIndexEntry
from halite.jobs.ingest import refresh_active_jids, refresh_jobs_index


@pytest.mark.asyncio
async def test_refresh_jobs_index_inserts_rows(session):
    salt = AsyncMock()
    salt.runner_call.return_value = {
        "20260527120000000001": {
            "Function": "state.apply",
            "Target": "*",
            "Target-type": "glob",
            "User": "saltapi",
            "StartTime": "2026, May 27 12:00:00.000001",
            "Arguments": [],
        },
        "20260527130000000002": {
            "Function": "test.ping",
            "Target": "web-1",
            "Target-type": "glob",
            "User": "root",
            "StartTime": "2026, May 27 13:00:00.000002",
            "Arguments": [],
        },
    }
    written = await refresh_jobs_index(session, salt)
    await session.commit()
    rows = (await session.execute(select(JobIndexEntry))).scalars().all()
    assert written == 2
    by_jid = {r.jid: r for r in rows}
    assert by_jid["20260527120000000001"].function == "state.apply"
    assert by_jid["20260527130000000002"].target == "web-1"


@pytest.mark.asyncio
async def test_refresh_jobs_index_is_idempotent(session):
    salt = AsyncMock()
    salt.runner_call.return_value = {
        "20260527120000000001": {
            "Function": "state.apply",
            "Target": "*",
            "Target-type": "glob",
            "User": "saltapi",
            "StartTime": "2026, May 27 12:00:00.000001",
            "Arguments": [],
        },
    }
    await refresh_jobs_index(session, salt)
    await session.commit()
    await refresh_jobs_index(session, salt)
    await session.commit()
    rows = (await session.execute(select(JobIndexEntry))).scalars().all()
    assert len(rows) == 1


@pytest.mark.asyncio
async def test_refresh_jobs_index_skips_unparseable_jids(session):
    salt = AsyncMock()
    salt.runner_call.return_value = {
        "not-a-jid": {"Function": "x", "StartTime": "garbage"},
        "20260527120000000001": {
            "Function": "state.apply",
            "Target": "*",
            "Target-type": "glob",
            "User": "saltapi",
            "StartTime": "2026, May 27 12:00:00.000001",
            "Arguments": [],
        },
    }
    written = await refresh_jobs_index(session, salt)
    await session.commit()
    rows = (await session.execute(select(JobIndexEntry))).scalars().all()
    assert written == 1
    assert rows[0].jid == "20260527120000000001"


@pytest.mark.asyncio
async def test_refresh_active_jids_returns_set():
    salt = AsyncMock()
    salt.list_active_jobs.return_value = {
        "20260527120000000001": {"Function": "state.apply"},
        "20260527130000000002": {"Function": "test.ping"},
    }
    result = await refresh_active_jids(salt)
    assert result == {"20260527120000000001", "20260527130000000002"}


@pytest.mark.asyncio
async def test_refresh_active_jids_returns_empty_on_failure():
    salt = AsyncMock()
    salt.list_active_jobs.side_effect = Exception("boom")
    result = await refresh_active_jids(salt)
    assert result == set()
