from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from halite.fleet.models import HighstateRun
from halite.minions.schemas import (
    MinionComplianceBucket,
    MinionComplianceOut,
    MinionRunsOut,
    MinionRunSummary,
    RunStatus,
)


def _status_for(row: HighstateRun) -> RunStatus:
    if row.blocked:
        return "blocked"
    if row.fail_count > 0:
        return "unhealthy"
    if row.change_count > 0:
        return "changed"
    return "healthy"


def _anchor_utc(d: datetime) -> datetime:
    return d if d.tzinfo is not None else d.replace(tzinfo=UTC)


async def list_runs(
    db: AsyncSession, minion_id: str, *, limit: int
) -> MinionRunsOut:
    rows = (
        await db.execute(
            select(HighstateRun)
            .where(HighstateRun.minion_id == minion_id)
            .order_by(desc(HighstateRun.completed_at))
            .limit(limit)
        )
    ).scalars().all()
    runs = [
        MinionRunSummary(
            id=r.id,
            jid=r.jid,
            fun=r.fun,
            completed_at=_anchor_utc(r.completed_at),
            pass_count=r.pass_count,
            fail_count=r.fail_count,
            change_count=r.change_count,
            total_count=r.total_count,
            duration_ms=r.duration_ms,
            blocked=r.blocked,
            status=_status_for(r),
        )
        for r in rows
    ]
    return MinionRunsOut(minion_id=minion_id, total=len(runs), runs=runs)


async def list_compliance(
    db: AsyncSession, minion_id: str, *, limit: int
) -> MinionComplianceOut:
    """Per-minion compliance series — one bucket per recent run, oldest-first
    so the sparkline reads left-to-right."""
    rows = (
        await db.execute(
            select(HighstateRun)
            .where(HighstateRun.minion_id == minion_id)
            .order_by(desc(HighstateRun.completed_at))
            .limit(limit)
        )
    ).scalars().all()
    rows = list(reversed(rows))
    buckets = [
        MinionComplianceBucket(
            completed_at=_anchor_utc(r.completed_at),
            jid=r.jid,
            pass_count=r.pass_count,
            fail_count=r.fail_count,
            change_count=r.change_count,
            total_count=r.total_count,
            status=_status_for(r),
        )
        for r in rows
    ]
    return MinionComplianceOut(minion_id=minion_id, buckets=buckets)
