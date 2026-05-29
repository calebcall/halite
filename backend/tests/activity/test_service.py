from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select

from halite.activity.models import ActivityEvent
from halite.activity.normalize import normalize_event
from halite.activity.service import persist_event, prune_events


async def test_persist_event_writes_row(session):
    ev = normalize_event("salt/minion/web01/start", {"id": "web01"})
    await persist_event(session, ev)
    await session.commit()
    count = await session.scalar(select(func.count()).select_from(ActivityEvent))
    assert count == 1


async def test_prune_events_deletes_old(session):
    old = ActivityEvent(
        ts=datetime.now(tz=UTC) - timedelta(days=40),
        category="job", event_type="job.new", summary="old",
    )
    fresh = ActivityEvent(
        ts=datetime.now(tz=UTC), category="job", event_type="job.new", summary="new",
    )
    session.add_all([old, fresh])
    await session.commit()
    deleted = await prune_events(session, retention_days=30)
    await session.commit()
    assert deleted == 1
    remaining = await session.scalar(select(func.count()).select_from(ActivityEvent))
    assert remaining == 1
