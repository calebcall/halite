from datetime import UTC, datetime

import pytest
from sqlalchemy import select

from halite.activity.models import ActivityEvent


def test_activity_event_columns_exist():
    ev = ActivityEvent(
        ts=datetime.now(tz=UTC),
        category="job",
        event_type="job.ret",
        minion_id="web01",
        jid="20260529120000000000",
        fun="state.apply",
        success=True,
        summary="web01 returned state.apply",
        raw={"tag": "salt/job/x/ret/web01", "data": {}},
    )
    assert ev.category == "job"
    assert ev.jid == "20260529120000000000"
    assert ev.success is True
    assert ActivityEvent.__tablename__ == "activity_events"


@pytest.mark.asyncio
async def test_activity_event_round_trip(session):
    ev = ActivityEvent(
        ts=datetime.now(tz=UTC),
        category="job",
        event_type="job.ret",
        minion_id="web01",
        jid="20260529120000000000",
        fun="state.apply",
        success=True,
        summary="web01 returned state.apply",
        raw={"tag": "salt/job/x/ret/web01", "data": {"retcode": 0}},
    )
    session.add(ev)
    await session.commit()

    row = (await session.execute(select(ActivityEvent).where(ActivityEvent.id == ev.id))).scalar_one()
    assert row.category == "job"
    assert row.jid == "20260529120000000000"
    assert row.success is True
    assert row.raw == {"tag": "salt/job/x/ret/web01", "data": {"retcode": 0}}
