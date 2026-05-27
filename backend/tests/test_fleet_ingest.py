from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select

from halite.fleet.ingest import ingest_recent_highstates
from halite.fleet.models import HighstateRun


@pytest.mark.asyncio
async def test_ingest_writes_one_row_per_minion(session):
    salt = AsyncMock()
    salt.runner_call.side_effect = [
        {"20260526120000000001": {"Function": "state.apply", "StartTime": "2026, May 26 12:00:00.000000"}},
        {
            "Function": "state.apply",
            "StartTime": "2026, May 26 12:00:00.000000",
            "Result": {
                "minion-a": {
                    "return": {
                        "pkg_|-redis_|-redis_|-installed": {
                            "result": True, "comment": "", "changes": {},
                            "duration": 100.0, "__run_num__": 1,
                        }
                    },
                    "retcode": 0,
                    "success": True,
                },
                "minion-b": {
                    "return": {
                        "pkg_|-redis_|-redis_|-installed": {
                            "result": False, "comment": "boom", "changes": {},
                            "duration": 50.0, "__run_num__": 1,
                        }
                    },
                    "retcode": 1,
                    "success": False,
                },
            },
        },
    ]

    count = await ingest_recent_highstates(
        session, salt, funs=["state.apply"], lookback_minutes=60 * 24 * 365 * 10
    )
    await session.commit()

    rows = (await session.execute(select(HighstateRun))).scalars().all()
    assert count == 2
    assert {r.minion_id for r in rows} == {"minion-a", "minion-b"}
    by_minion = {r.minion_id: r for r in rows}
    assert by_minion["minion-a"].pass_count == 1
    assert by_minion["minion-b"].fail_count == 1


@pytest.mark.asyncio
async def test_ingest_is_idempotent_on_minion_jid(session):
    salt = AsyncMock()
    _list_job_response = {
        "Function": "state.apply",
        "StartTime": "2026, May 26 12:00:00.000000",
        "Result": {
            "minion-a": {
                "return": {"pkg_|-redis_|-redis_|-installed": {"result": True, "comment": "", "changes": {}, "duration": 100.0, "__run_num__": 1}},
                "retcode": 0,
                "success": True,
            }
        },
    }
    salt.runner_call.side_effect = [
        {"20260526120000000001": {"Function": "state.apply", "StartTime": "2026, May 26 12:00:00.000000"}},
        _list_job_response,
        {"20260526120000000001": {"Function": "state.apply", "StartTime": "2026, May 26 12:00:00.000000"}},
        _list_job_response,
    ]
    await ingest_recent_highstates(session, salt, funs=["state.apply"], lookback_minutes=60 * 24 * 365 * 10)
    await session.commit()
    await ingest_recent_highstates(session, salt, funs=["state.apply"], lookback_minutes=60 * 24 * 365 * 10)
    await session.commit()
    rows = (await session.execute(select(HighstateRun))).scalars().all()
    assert len(rows) == 1


@pytest.mark.asyncio
async def test_ingest_records_blocked_minions(session):
    salt = AsyncMock()
    salt.runner_call.side_effect = [
        {"20260526120000000001": {"Function": "state.apply", "StartTime": "2026, May 26 12:00:00.000000"}},
        {
            "Function": "state.apply",
            "StartTime": "2026, May 26 12:00:00.000000",
            "Result": {
                "minion-a": {
                    "return": "Minion did not return. [No response]",
                    "retcode": 1,
                    "success": False,
                },
            },
        },
    ]
    count = await ingest_recent_highstates(
        session, salt, funs=["state.apply"], lookback_minutes=60 * 24 * 365 * 10
    )
    await session.commit()
    rows = (await session.execute(select(HighstateRun))).scalars().all()
    assert count == 1
    assert rows[0].blocked is True
    assert rows[0].total_count == 0
