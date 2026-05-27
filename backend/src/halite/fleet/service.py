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


def _status_for(
    run: HighstateRun | None, *, online: bool, now: datetime
) -> HealthStatus:
    if not online:
        return "unhealthy"
    if run is None:
        return "unknown"
    if run.blocked:
        return "blocked"
    # SQLite drops timezone info; treat naive datetimes as UTC.
    completed = run.completed_at
    if completed.tzinfo is None:
        completed = completed.replace(tzinfo=UTC)
    if (now - completed) > _STALE_AFTER:
        return "stale"
    if run.fail_count > 0:
        return "unhealthy"
    if run.change_count > 0:
        return "changed"
    return "healthy"


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


async def fleet_health(
    db: AsyncSession, *, connected: set[str]
) -> list[MinionHealthOut]:
    """Build the heatmap rows. `connected` is the set of minion_ids that
    are currently reachable on the master (from manage.present). The
    output is the UNION of (minions with at least one ingested run) and
    (currently-connected minions) — so an offline minion that has never
    ingested still appears, flagged as unhealthy."""
    now = datetime.now(tz=UTC)
    runs = await latest_per_minion(db)
    by_minion: dict[str, HighstateRun] = {r.minion_id: r for r in runs}

    minion_ids = set(by_minion) | connected
    out: list[MinionHealthOut] = []
    for mid in sorted(minion_ids):
        run = by_minion.get(mid)
        online = mid in connected
        status = _status_for(run, online=online, now=now)
        if run is None:
            out.append(MinionHealthOut(
                minion_id=mid,
                online=online,
                run_id=None,
                jid=None,
                completed_at=None,
                status=status,
                pass_count=0,
                fail_count=0,
                change_count=0,
                total_count=0,
                duration_ms=0,
            ))
        else:
            out.append(MinionHealthOut(
                minion_id=mid,
                online=online,
                run_id=run.id,
                jid=run.jid,
                completed_at=run.completed_at,
                status=status,
                pass_count=run.pass_count,
                fail_count=run.fail_count,
                change_count=run.change_count,
                total_count=run.total_count,
                duration_ms=run.duration_ms,
            ))
    return out


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
