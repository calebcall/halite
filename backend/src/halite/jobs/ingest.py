from __future__ import annotations

import logging
import re
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from halite.jobs.index_model import JobIndexEntry

log = logging.getLogger(__name__)

# Salt JIDs are timestamp-derived: YYYYMMDDHHMMSSffffff (microsecond precision).
_JID_RE = re.compile(r"^\d{20}$")


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


async def refresh_jobs_index(db: AsyncSession, salt: Any) -> int:
    """Fetch ``runner.jobs.list_jobs`` and upsert each row into
    ``jobs_index``. Returns the number of rows written this call (insert
    or update)."""
    raw = await salt.runner_call("jobs.list_jobs")
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
