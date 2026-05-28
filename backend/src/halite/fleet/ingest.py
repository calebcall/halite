from __future__ import annotations

import logging
import re
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from halite.fleet.models import HighstateRun
from halite.fleet.parser import summarize_lowstate
from halite.jobs.index_model import JobIndexEntry

log = logging.getLogger(__name__)

# Salt StartTime format: "2026, May 26 12:00:00.000000"
_SALT_DT = re.compile(r"^(\d{4}), (\w+) (\d{1,2}) (\d{2}):(\d{2}):(\d{2})")
_MONTHS = {
    "April": 4,
    "August": 8,
    "December": 12,
    "February": 2,
    "January": 1,
    "July": 7,
    "June": 6,
    "March": 3,
    "May": 5,
    "November": 11,
    "October": 10,
    "September": 9,
}

# Common "minion didn't return" sentinels salt emits when a minion is
# offline or actively running another job ("salt-busy").
_BLOCKED_PREFIXES = ("Minion did not return", "Salt request timed out")


def _parse_salt_time(s: str | None) -> datetime:
    if not isinstance(s, str):
        return datetime.now(tz=UTC)
    m = _SALT_DT.match(s)
    if not m:
        return datetime.now(tz=UTC)
    y, mon, d, hh, mm, ss = m.groups()
    return datetime(int(y), _MONTHS.get(mon, 1), int(d), int(hh), int(mm), int(ss), tzinfo=UTC)


def _is_blocked(value: Any) -> bool:
    if isinstance(value, str):
        return any(value.startswith(p) for p in _BLOCKED_PREFIXES)
    return False


async def ingest_recent_highstates(
    db: AsyncSession,
    salt: Any,  # SaltAPIClient duck-typed
    *,
    funs: list[str],
    lookback_minutes: int = 60,
) -> int:
    """Read recent state.* jids from ``jobs_index`` and persist their
    per-minion results into ``highstate_runs``.

    We DELIBERATELY do not call ``runner.jobs.list_jobs`` here — on
    masters with large job caches that response drops mid-stream and the
    fleet scheduler ends up failing every tick (we observed this against
    a master with thousands of cached jobs, dropping at 2.7 MB of a 16.7
    MB payload). The jobs-index poller already does the heavy lifting of
    discovering jids using a server-side ``start_time`` filter, and we
    inherit that work for free.

    Idempotent on (minion_id, jid). Skips jids already fully ingested.
    Returns the number of rows written this run.
    """
    cutoff = datetime.now(tz=UTC) - timedelta(minutes=lookback_minutes)
    # Source of truth: jobs_index rows for state.* functions in the window.
    candidates = (
        await db.execute(
            select(JobIndexEntry).where(
                JobIndexEntry.started_at >= cutoff,
                JobIndexEntry.function.in_(funs),
            )
        )
    ).scalars().all()
    if not candidates:
        return 0

    # Pre-fetch jids that already have any highstate_runs row so we skip
    # them. A jid present means it's been processed (at least partially);
    # don't refetch.
    already_ingested = {
        r for r in (
            await db.execute(
                select(HighstateRun.jid).where(
                    HighstateRun.jid.in_([c.jid for c in candidates])
                )
            )
        ).scalars().all()
    }

    written = 0
    for entry in candidates:
        if entry.jid in already_ingested:
            continue
        fun = entry.function
        started = entry.started_at
        if started.tzinfo is None:
            started = started.replace(tzinfo=UTC)

        try:
            job = await salt.runner_call("jobs.list_job", jid=entry.jid)
        except Exception:
            log.exception("ingest: list_job failed for %s", entry.jid)
            continue
        if not isinstance(job, dict):
            continue
        returns_section = job.get("Result")
        if not isinstance(returns_section, dict):
            continue

        jid = entry.jid
        for minion_id, entry_value in returns_section.items():
            # list_job wraps each minion result: {"return": <state-dict>, "retcode": int, ...}
            # Fall back to the entry itself for salt versions that return the
            # state dict directly (or a plain string sentinel for blocked minions).
            raw_result = (
                entry_value["return"]
                if isinstance(entry_value, dict) and "return" in entry_value
                else entry_value
            )
            existing = (
                await db.execute(
                    select(HighstateRun.id).where(
                        HighstateRun.minion_id == minion_id,
                        HighstateRun.jid == jid,
                    )
                )
            ).scalar_one_or_none()
            if existing is not None:
                continue

            if _is_blocked(raw_result):
                row = HighstateRun(
                    blocked=True,
                    change_count=0,
                    completed_at=started,
                    duration_ms=0,
                    fail_count=0,
                    fun=fun,
                    jid=jid,
                    minion_id=minion_id,
                    pass_count=0,
                    raw_result={"_blocked": raw_result if isinstance(raw_result, str) else None},
                    total_count=0,
                )
                db.add(row)
                written += 1
                continue

            counts = summarize_lowstate(raw_result)
            if counts is None:
                # Not a parseable state return; skip silently.
                continue
            row = HighstateRun(
                blocked=False,
                change_count=counts.changed,
                completed_at=started,
                duration_ms=counts.duration_ms,
                fail_count=counts.failed,
                fun=fun,
                jid=jid,
                minion_id=minion_id,
                pass_count=counts.passed,
                raw_result=raw_result,
                total_count=counts.total,
            )
            db.add(row)
            written += 1
    if written:
        await db.flush()
    return written
