from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import delete
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
        summary=ev["summary"],
        raw=ev["raw"],
    )
    db.add(row)
    return row


async def prune_events(db: AsyncSession, *, retention_days: int) -> int:
    cutoff = datetime.now(tz=UTC) - timedelta(days=retention_days)
    result = await db.execute(delete(ActivityEvent).where(ActivityEvent.ts < cutoff))
    return result.rowcount or 0
