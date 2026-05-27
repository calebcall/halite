from __future__ import annotations

import logging
import re
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from halite.fleet.models import HighstateRun
from halite.fleet.parser import summarize_lowstate

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
    """Pull recent highstate jobs from salt and persist parsed summaries.

    Returns the number of rows written this run. Idempotent on (minion_id, jid).
    """
    cutoff = datetime.now(tz=UTC) - timedelta(minutes=lookback_minutes)
    jobs = await salt.runner_call("jobs.list_jobs", search_function=funs)
    if not isinstance(jobs, dict):
        log.warning("ingest: list_jobs returned non-dict %r", type(jobs).__name__)
        return 0

    written = 0
    for jid, meta in jobs.items():
        if not isinstance(meta, dict):
            continue
        fun = meta.get("Function")
        if fun not in funs:
            continue
        started = _parse_salt_time(meta.get("StartTime"))
        if started < cutoff:
            continue

        try:
            returns = await salt.runner_call("jobs.lookup_jid", jid=jid)
        except Exception:
            log.exception("ingest: lookup_jid failed for %s", jid)
            continue
        if not isinstance(returns, dict):
            continue

        for minion_id, raw_result in returns.items():
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
