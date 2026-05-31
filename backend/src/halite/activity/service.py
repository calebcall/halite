from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import and_, delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from halite.activity.models import ActivityEvent
from halite.activity.normalize import NormalizedEvent


async def persist_event(db: AsyncSession, ev: NormalizedEvent) -> ActivityEvent:
    row = ActivityEvent(
        ts=datetime.now(tz=UTC),
        category=ev["category"],
        event_type=ev["event_type"],
        minion_id=ev["minion_id"],
        jid=ev["jid"],
        fun=ev["fun"],
        success=ev["success"],
        changed=ev["changed"],
        initiator=ev["initiator"],
        target=ev["target"],
        duration_ms=ev["duration_ms"],
        summary=ev["summary"],
        raw=ev["raw"],
    )
    db.add(row)
    return row


async def list_events(
    db: AsyncSession,
    *,
    allowed_categories: set[str],
    category: str | None = None,
    categories: list[str] | None = None,
    minion_id: str | None = None,
    event_type: str | None = None,
    search: str | None = None,
    hide_routine: bool = False,
    hide_dispatch: bool = False,
    since_minutes: int | None = None,
    limit: int = 100,
    offset: int = 0,
):
    if not allowed_categories:
        return 0, []
    # Start from what the user is permitted to see, then narrow by the optional
    # multi-category set and the single-category filter (both intersected in).
    cats = set(allowed_categories)
    if categories is not None:
        cats &= set(categories)
    if category is not None:
        cats &= {category}
    if not cats:
        return 0, []
    base = select(ActivityEvent).where(ActivityEvent.category.in_(cats))
    if minion_id:
        base = base.where(ActivityEvent.minion_id == minion_id)
    if event_type:
        base = base.where(ActivityEvent.event_type == event_type)
    if search:
        like = f"%{search}%"
        base = base.where(
            or_(
                ActivityEvent.summary.ilike(like),
                ActivityEvent.minion_id.ilike(like),
                ActivityEvent.fun.ilike(like),
                ActivityEvent.initiator.ilike(like),
                ActivityEvent.target.ilike(like),
            )
        )
    if hide_routine:
        # Exclude routine successes: job.ret rows that succeeded and made no
        # changes (changed false-or-null). Failures, changes, and all non-job.ret
        # events are kept.
        routine = and_(
            ActivityEvent.event_type == "job.ret",
            ActivityEvent.success.is_(True),
            ActivityEvent.changed.is_not(True),
        )
        base = base.where(~routine)
    if hide_dispatch:
        base = base.where(ActivityEvent.event_type != "job.new")
    if since_minutes is not None:
        cutoff = datetime.now(tz=UTC) - timedelta(minutes=since_minutes)
        base = base.where(ActivityEvent.ts >= cutoff)
    total = await db.scalar(select(func.count()).select_from(base.subquery()))
    rows = (
        await db.execute(
            base.order_by(ActivityEvent.ts.desc()).limit(limit).offset(offset)
        )
    ).scalars().all()
    return int(total or 0), list(rows)


async def prune_events(db: AsyncSession, *, retention_days: int) -> int:
    cutoff = datetime.now(tz=UTC) - timedelta(days=retention_days)
    result = await db.execute(delete(ActivityEvent).where(ActivityEvent.ts < cutoff))
    return result.rowcount or 0
