from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from halite.minions.service import _pick_primary_ip  # noqa: PLC2701
from halite.minions.snapshot_model import MinionSnapshot

log = logging.getLogger(__name__)

_KEY_STATUS_BY_BUCKET = {
    "minions": "accepted",
    "minions_pre": "pending",
    "minions_rejected": "rejected",
    "minions_denied": "denied",
}


async def refresh_keys(db: AsyncSession, salt: Any) -> int:
    """Reconcile minion_snapshots against wheel.key.list_all. Inserts
    rows for new keys, updates status when it changes, and deletes rows
    whose key has vanished. Returns the number of rows touched."""
    keys = await salt.list_minion_keys()
    if not isinstance(keys, dict):
        return 0

    desired_status: dict[str, str] = {}
    for bucket, status in _KEY_STATUS_BY_BUCKET.items():
        for mid in keys.get(bucket, []) or []:
            desired_status[str(mid)] = status

    now = datetime.now(tz=UTC)
    rows = (await db.execute(select(MinionSnapshot))).scalars().all()
    by_id = {r.minion_id: r for r in rows}

    touched = 0
    for mid, status in desired_status.items():
        row = by_id.get(mid)
        if row is None:
            db.add(MinionSnapshot(
                minion_id=mid,
                key_status=status,
                online=False,
                keys_refreshed_at=now,
            ))
            touched += 1
        elif row.key_status != status:
            row.key_status = status
            row.keys_refreshed_at = now
            touched += 1
        else:
            row.keys_refreshed_at = now

    for mid, row in by_id.items():
        if mid not in desired_status:
            await db.delete(row)
            touched += 1
    return touched


async def refresh_presence(db: AsyncSession, salt: Any) -> int:
    """Update the ``online`` field on every existing snapshot row using
    runner.manage.present. Does NOT create new rows — keys are the
    source of truth for who exists."""
    present = await salt.list_present_minion_ids()
    if not isinstance(present, set):
        present = set(present)
    now = datetime.now(tz=UTC)
    rows = (await db.execute(select(MinionSnapshot))).scalars().all()
    touched = 0
    for row in rows:
        new_online = row.minion_id in present
        if row.online != new_online:
            row.online = new_online
            touched += 1
        row.presence_refreshed_at = now
    return touched


def _str_or_none(v: Any) -> str | None:
    if v is None:
        return None
    s = str(v)
    return s if s else None


def _denorm(row: MinionSnapshot, grains: dict[str, Any]) -> None:
    row.os = _str_or_none(grains.get("os"))
    row.os_family = _str_or_none(grains.get("os_family"))
    row.osrelease = _str_or_none(grains.get("osrelease"))
    row.kernel = _str_or_none(grains.get("kernel"))
    row.kernelrelease = _str_or_none(grains.get("kernelrelease"))
    row.virtual_type = _str_or_none(grains.get("virtual"))
    row.saltversion = _str_or_none(grains.get("saltversion"))
    cpus = grains.get("num_cpus")
    row.num_cpus = int(cpus) if isinstance(cpus, int | float) else None
    mem = grains.get("mem_total")
    row.mem_total_mb = int(mem) if isinstance(mem, int | float) else None
    row.primary_ip = _pick_primary_ip(grains)


async def refresh_grains(db: AsyncSession, salt: Any) -> int:
    """Pull master-cached grains for every minion and update its snapshot.
    Rows without an existing snapshot are skipped — keys are the source
    of truth."""
    cache = await salt.cache_grains()
    if not isinstance(cache, dict):
        return 0
    now = datetime.now(tz=UTC)
    rows = (await db.execute(select(MinionSnapshot))).scalars().all()
    by_id = {r.minion_id: r for r in rows}
    touched = 0
    for mid, grains in cache.items():
        row = by_id.get(mid)
        if row is None or not isinstance(grains, dict):
            continue
        row.grains = grains
        _denorm(row, grains)
        row.grains_refreshed_at = now
        touched += 1
    return touched
