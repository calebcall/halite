from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select

from halite.activity.models import ActivityEvent
from halite.activity.normalize import normalize_event
from halite.activity.service import list_events, persist_event, prune_events


async def test_persist_event_writes_row(session):
    ev = normalize_event("salt/minion/web01/start", {"id": "web01"})
    await persist_event(session, ev)
    await session.commit()
    count = await session.scalar(select(func.count()).select_from(ActivityEvent))
    assert count == 1


async def test_list_events_categories_filter(session):
    now = datetime.now(tz=UTC)
    session.add_all([
        ActivityEvent(ts=now, category="job", event_type="job.ret", summary="j"),
        ActivityEvent(ts=now, category="key", event_type="key_accept", summary="k"),
        ActivityEvent(ts=now, category="minion", event_type="minion_start", summary="m"),
    ])
    await session.commit()

    allowed = {"job", "key", "minion"}
    total, rows = await list_events(session, allowed_categories=allowed, categories=["job"])
    assert total == 1
    assert {r.category for r in rows} == {"job"}

    # categories intersected with allowed: a category not allowed is dropped
    total, _ = await list_events(session, allowed_categories={"job"}, categories=["job", "key"])
    assert total == 1

    # empty intersection -> nothing
    total, rows = await list_events(session, allowed_categories={"job"}, categories=["key"])
    assert total == 0
    assert rows == []


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
