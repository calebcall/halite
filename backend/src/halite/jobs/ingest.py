from __future__ import annotations

import logging
import re
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from halite.jobs.index_model import JobIndexEntry

log = logging.getLogger(__name__)

# Salt JIDs are timestamp-derived: YYYYMMDDHHMMSSffffff (microsecond precision).
_JID_RE = re.compile(r"^\d{20}$")

# Default window for jobs.list_jobs. Without a start_time, big masters return
# the entire cache (potentially MBs) and the salt-api connection drops mid-
# stream. 4 hours is wide enough to catch up after a brief poller outage but
# narrow enough to keep payload sizes well under salt-api's streaming limits.
_DEFAULT_LOOKBACK_HOURS = 4
# Salt's start_time arg accepts this format (used by salt internally).
_SALT_TIME_FMT = "%Y, %b %d %H:%M:%S.%f"


def _jid_to_utc(jid: str) -> datetime | None:
    """Parse a salt JID into a UTC datetime. Returns None on bad input."""
    if not _JID_RE.match(jid):
        return None
    try:
        return datetime(
            int(jid[0:4]), int(jid[4:6]), int(jid[6:8]),
            int(jid[8:10]), int(jid[10:12]), int(jid[12:14]),
            int(jid[14:20]), tzinfo=UTC,
        )
    except ValueError:
        return None


def _opt_str(v: Any) -> str | None:
    if v is None:
        return None
    s = str(v)
    return s if s else None


async def refresh_jobs_index(
    db: AsyncSession,
    salt: Any,
    *,
    lookback_hours: int = _DEFAULT_LOOKBACK_HOURS,
) -> int:
    """Fetch ``runner.jobs.list_jobs`` with a ``start_time`` window and
    upsert each row into ``jobs_index``. Returns the number of rows
    written this call.

    We pass ``start_time`` because masters with large job caches drop
    the connection partway through streaming an unfiltered response (we
    observed a master cut us off at 2.7 MB of a 16.7 MB payload). 4
    hours of jobs is roughly 1.5–2 MB on a busy fleet — well within
    salt-api's streaming budget. The 90s timeout absorbs slow masters;
    a single attempt is fine because the next scheduler tick (300s
    default) will retry naturally.
    """
    start_time = (
        datetime.now(tz=UTC) - timedelta(hours=lookback_hours)
    ).strftime(_SALT_TIME_FMT)
    raw = await salt.runner_call(
        "jobs.list_jobs",
        timeout=90.0,
        max_retries=1,
        start_time=start_time,
    )
    if not isinstance(raw, dict):
        return 0
    now = datetime.now(tz=UTC)
    existing_jids = {
        r for r in (await db.execute(select(JobIndexEntry.jid))).scalars().all()
    }
    written = 0
    for jid, meta in raw.items():
        if not isinstance(jid, str) or not isinstance(meta, dict):
            continue
        started = _jid_to_utc(jid)
        if started is None:
            continue
        args = meta.get("Arguments")
        if jid in existing_jids:
            row = (
                await db.execute(
                    select(JobIndexEntry).where(JobIndexEntry.jid == jid)
                )
            ).scalar_one()
            row.seen_at = now
            written += 1
        else:
            db.add(JobIndexEntry(
                jid=jid,
                function=str(meta.get("Function") or ""),
                target=_opt_str(meta.get("Target")),
                target_type=_opt_str(meta.get("Target-type")),
                user=_opt_str(meta.get("User")),
                started_at=started,
                seen_at=now,
                arguments=args if isinstance(args, list | dict) else None,
            ))
            written += 1
    return written


async def upsert_one_job(
    db: AsyncSession, jid: str, new_event_data: dict[str, Any]
) -> None:
    """Upsert a single job into jobs_index from a ``salt/job/<jid>/new`` event.

    ``new_event_data`` is the event payload: {fun, arg, tgt, tgt_type, user,
    minions, ...}. Mirrors the JobIndexEntry mapping used in
    refresh_jobs_index but reads the event's lowercase keys.  ``arguments``
    is stored as the raw value (list or dict), matching the shape written by
    refresh_jobs_index.
    """
    started = _jid_to_utc(jid)
    if started is None:
        return
    now = datetime.now(tz=UTC)
    existing = await db.get(JobIndexEntry, jid)
    if existing is not None:
        existing.seen_at = now
        return
    arg = new_event_data.get("arg")
    db.add(
        JobIndexEntry(
            jid=jid,
            function=str(new_event_data.get("fun") or "unknown"),
            target=_opt_str(new_event_data.get("tgt")),
            target_type=_opt_str(new_event_data.get("tgt_type")),
            user=_opt_str(new_event_data.get("user")),
            started_at=started,
            seen_at=now,
            arguments=arg if isinstance(arg, list | dict) else None,
        )
    )


async def refresh_active_jids(salt: Any) -> set[str]:
    """Return the set of currently-active jids via ``runner.jobs.active``
    (which already has a short timeout per the salt client). Returns an
    empty set on failure — the caller decides how to surface unknown
    state."""
    try:
        active = await salt.list_active_jobs()
    except Exception:
        log.exception("refresh_active_jids: list_active_jobs failed")
        return set()
    if not isinstance(active, dict):
        return set()
    return {str(k) for k in active}
