from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from halite.minions.schemas import (
    MinionDetail,
    MinionListOut,
    MinionStatus,
    MinionSummary,
)
from halite.minions.snapshot_model import MinionSnapshot

# 10 minutes after the oldest cadence is "stale" enough that we flag the
# UI badge. Tuned to ~2x the recommended cadence (5 min keys/grains).
_STALE_AFTER = timedelta(minutes=10)


def _status_from(row: MinionSnapshot) -> MinionStatus:
    if row.key_status == "accepted":
        return "online" if row.online else "offline"
    if row.key_status == "pending":
        return "pending"
    if row.key_status == "rejected":
        return "rejected"
    if row.key_status == "denied":
        return "denied"
    # Defensive: unknown key_status falls back to offline.
    return "offline"


def _row_oldest_refresh(row: MinionSnapshot) -> datetime | None:
    candidates = [
        row.keys_refreshed_at,
        row.presence_refreshed_at,
        row.grains_refreshed_at,
    ]
    populated = [c for c in candidates if c is not None]
    if not populated:
        return None
    return min(populated)


def _anchor_to_utc(d: datetime) -> datetime:
    # SQLite drops tz info on read; treat naive datetimes as UTC.
    return d if d.tzinfo is not None else d.replace(tzinfo=UTC)


async def list_minions_from_db(db: AsyncSession) -> MinionListOut:
    rows = (
        await db.execute(select(MinionSnapshot).order_by(MinionSnapshot.minion_id))
    ).scalars().all()

    minions = [
        MinionSummary(
            id=r.minion_id,
            ip=r.primary_ip,
            status=_status_from(r),
            os=r.os,
            os_family=r.os_family,
            osrelease=r.osrelease,
            saltversion=r.saltversion,
        )
        for r in rows
    ]

    oldest: datetime | None = None
    for r in rows:
        rr = _row_oldest_refresh(r)
        if rr is None:
            continue
        if oldest is None or rr < oldest:
            oldest = rr

    is_stale = False
    if oldest is not None:
        anchored = _anchor_to_utc(oldest)
        is_stale = (datetime.now(tz=UTC) - anchored) > _STALE_AFTER

    return MinionListOut(
        total=len(minions),
        minions=minions,
        last_refreshed_at=oldest,
        is_stale=is_stale,
    )


async def get_minion_from_db(
    db: AsyncSession, minion_id: str
) -> MinionDetail | None:
    row = (
        await db.execute(
            select(MinionSnapshot).where(MinionSnapshot.minion_id == minion_id)
        )
    ).scalar_one_or_none()
    if row is None:
        return None

    oldest = _row_oldest_refresh(row)
    is_stale = False
    if oldest is not None:
        is_stale = (datetime.now(tz=UTC) - _anchor_to_utc(oldest)) > _STALE_AFTER

    return MinionDetail(
        id=row.minion_id,
        status=_status_from(row),
        ip=row.primary_ip,
        grains=row.grains,
        last_refreshed_at=oldest,
        is_stale=is_stale,
    )
