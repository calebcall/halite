from __future__ import annotations

import uuid
from collections import Counter
from datetime import UTC, datetime, timedelta

from sqlalchemy import Integer, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from halite.fleet.models import HighstateRun
from halite.fleet.parser import _LOWSTATE_KEY  # noqa: SLF001
from halite.fleet.schemas import (
    ComplianceBucketOut,
    HealthStatus,
    MinionHealthOut,
    TopFailureOut,
)

_STALE_AFTER = timedelta(days=2)


def _status_for(run: HighstateRun, now: datetime) -> HealthStatus:
    if run.blocked:
        return "blocked"
    if (now - run.completed_at) > _STALE_AFTER:
        return "stale"
    if run.fail_count > 0:
        return "fail"
    if run.change_count > 0:
        return "changed"
    return "pass"


async def latest_per_minion(db: AsyncSession) -> list[HighstateRun]:
    """Most-recent HighstateRun per minion_id (correlated-subquery form,
    portable across sqlite and postgres)."""
    latest_completed = (
        select(
            HighstateRun.minion_id.label("mid"),
            func.max(HighstateRun.completed_at).label("max_completed"),
        )
        .group_by(HighstateRun.minion_id)
        .subquery()
    )
    stmt = (
        select(HighstateRun)
        .join(
            latest_completed,
            (HighstateRun.minion_id == latest_completed.c.mid)
            & (HighstateRun.completed_at == latest_completed.c.max_completed),
        )
        .order_by(HighstateRun.minion_id.asc())
    )
    rows = await db.execute(stmt)
    return list(rows.scalars().all())


async def fleet_health(db: AsyncSession) -> list[MinionHealthOut]:
    now = datetime.now(tz=UTC)
    runs = await latest_per_minion(db)
    return [
        MinionHealthOut(
            minion_id=r.minion_id,
            run_id=r.id,
            jid=r.jid,
            completed_at=r.completed_at,
            status=_status_for(r, now),
            pass_count=r.pass_count,
            fail_count=r.fail_count,
            change_count=r.change_count,
            total_count=r.total_count,
            duration_ms=r.duration_ms,
        )
        for r in runs
    ]


async def compliance_series(
    db: AsyncSession, *, limit: int = 30
) -> list[ComplianceBucketOut]:
    """One bucket per recent jid (each highstate run is a bucket),
    fleet-aggregated. Returns oldest-first for left-to-right sparkline."""
    recent_jids_stmt = (
        select(HighstateRun.jid, func.max(HighstateRun.completed_at).label("c"))
        .group_by(HighstateRun.jid)
        .order_by(desc("c"))
        .limit(limit)
    )
    recent = (await db.execute(recent_jids_stmt)).all()
    if not recent:
        return []
    jids = [r.jid for r in recent]
    completed_by_jid = {r.jid: r.c for r in recent}

    agg_stmt = (
        select(
            HighstateRun.jid,
            func.sum(HighstateRun.pass_count).label("p"),
            func.sum(HighstateRun.fail_count).label("f"),
            func.sum(HighstateRun.change_count).label("c"),
            func.sum(func.cast(HighstateRun.blocked, Integer)).label("b"),
        )
        .where(HighstateRun.jid.in_(jids))
        .group_by(HighstateRun.jid)
    )
    agg = {row.jid: row for row in (await db.execute(agg_stmt)).all()}
    buckets: list[ComplianceBucketOut] = []
    for jid in jids:
        row = agg.get(jid)
        buckets.append(
            ComplianceBucketOut(
                bucketed_at=completed_by_jid[jid],
                pass_count=int(row.p or 0) if row else 0,
                fail_count=int(row.f or 0) if row else 0,
                change_count=int(row.c or 0) if row else 0,
                blocked_count=int(row.b or 0) if row else 0,
            )
        )
    buckets.sort(key=lambda b: b.bucketed_at)
    return buckets


async def top_failures(db: AsyncSession, *, limit: int = 10) -> list[TopFailureOut]:
    """Across the most-recent run per minion, count how many minions had
    each state fail. Returns top-N most-failed states fleet-wide."""
    runs = await latest_per_minion(db)
    counter: Counter[tuple[str, str, str]] = Counter()
    for r in runs:
        if r.blocked or not isinstance(r.raw_result, dict):
            continue
        for key, state in r.raw_result.items():
            if not isinstance(state, dict):
                continue
            if state.get("result") is not False:
                continue
            m = _LOWSTATE_KEY.match(key)
            if not m:
                continue
            counter[(m.group(2), m.group(3), m.group(4))] += 1
    most = counter.most_common(limit)
    return [
        TopFailureOut(state_id=sid, name=name, fun=fun, failure_count=n)
        for (sid, name, fun), n in most
    ]


async def get_run(db: AsyncSession, run_id: uuid.UUID) -> HighstateRun | None:
    return (
        await db.execute(select(HighstateRun).where(HighstateRun.id == run_id))
    ).scalar_one_or_none()
