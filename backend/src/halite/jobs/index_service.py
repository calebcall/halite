from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from halite.jobs.index_model import JobIndexEntry
from halite.jobs.schemas import (
    JobActivityBucket,
    JobActivityOut,
    JobsListOut,
    JobSummary,
)


def _anchor_utc(d: datetime) -> datetime:
    return d if d.tzinfo is not None else d.replace(tzinfo=UTC)


async def get_activity_from_db(
    db: AsyncSession,
    *,
    hours: int,
    active_jids: set[str] | None,
    last_polled_at: datetime | None,
) -> JobActivityOut:
    """Bucket jobs_index rows by hour over the last ``hours`` window.

    ``running`` is the size of the in-memory active-jids cache, which the
    scheduler refreshes alongside its list_jobs poll. If the cache is
    None (cold start), ``active_known`` flips to False and ``running``
    is reported as 0 — the UI surfaces that the scheduler hasn't yet
    ticked.
    """
    now = datetime.now(UTC).replace(minute=0, second=0, microsecond=0)
    window_start = now - timedelta(hours=hours - 1)

    rows = (
        await db.execute(
            select(JobIndexEntry.started_at).where(
                JobIndexEntry.started_at >= window_start
            )
        )
    ).scalars().all()

    counts = [0] * hours
    for started in rows:
        s = _anchor_utc(started)
        if s < window_start or s >= now + timedelta(hours=1):
            continue
        idx = int((s - window_start).total_seconds() // 3600)
        if 0 <= idx < hours:
            counts[idx] += 1

    buckets = [
        JobActivityBucket(
            hour_start=(window_start + timedelta(hours=i))
                .strftime("%Y-%m-%dT%H:%M:%SZ"),
            count=counts[i],
        )
        for i in range(hours)
    ]

    return JobActivityOut(
        hours=hours,
        buckets=buckets,
        total=sum(counts),
        running=len(active_jids) if active_jids is not None else 0,
        last_polled_at=last_polled_at,
        active_known=active_jids is not None,
    )


async def list_recent_jobs_from_db(
    db: AsyncSession,
    *,
    limit: int,
    active_jids: set[str] | None,
    last_polled_at: datetime | None,
) -> JobsListOut:
    """Most-recent ``limit`` rows from jobs_index ordered by started_at
    desc. ``status`` derives from in-memory active-jids cache — same
    semantic as the live path."""
    rows = (
        await db.execute(
            select(JobIndexEntry)
            .order_by(desc(JobIndexEntry.started_at))
            .limit(limit)
        )
    ).scalars().all()

    summaries: list[JobSummary] = []
    for r in rows:
        is_active = active_jids is not None and r.jid in active_jids
        summaries.append(JobSummary(
            jid=r.jid,
            function=r.function,
            target=r.target or "",
            target_type=r.target_type,
            user=r.user,
            start_time=_anchor_utc(r.started_at).strftime("%Y, %b %d %H:%M:%S.%f"),
            status="running" if is_active else "complete",
        ))
    return JobsListOut(
        total=len(summaries),
        jobs=summaries,
        last_polled_at=last_polled_at,
        active_known=active_jids is not None,
    )
