# backend/src/halite/inventory/service.py
"""High-level inventory operations: collect + persist + summary.

This layer owns the DB writes. The collector layer (``collectors.py``) is
pure: it fetches and parses. This layer takes a ``CollectorResult`` and
upserts it into the inventory tables.

Refresh strategy
----------------

``refresh_packages`` does a **delete-then-insert** per minion inside one
transaction:

  1. ``DELETE FROM inventory_package WHERE minion_id = ?``
  2. ``INSERT`` every entry from the collector
  3. Upsert the matching ``inventory_snapshot`` row.

This is dramatically simpler than tracking tombstones for removed packages,
and the volume per minion (a few thousand rows in the worst case for
Debian/Ubuntu) is small enough that the cost is negligible at our fleet
size. A future "history mode" would replace the DELETE with an UPDATE that
sets ``deleted_at``; the schema doesn't change.

The whole batch lives in one outer transaction. If any single minion fails
we roll back the entire refresh so the DB is never in an inconsistent state
(half-old, half-new) for the caller's view.
"""

from __future__ import annotations

import logging

from sqlalchemy import delete, distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from halite.inventory.collectors import (
    CollectorResult,
    collect_packages,
)
from halite.inventory.models import InventoryPackage, InventorySnapshot
from halite.inventory.schemas import (
    PackageAggregate,
    PackageAggregateOut,
    PackageQueryHit,
    PackageQueryIn,
    PackageQueryOut,
    VersionAggregate,
    VersionAggregateOut,
)
from halite.inventory.version_compare import satisfies
from halite.salt.client import SaltAPIClient

# When a query has a version filter we need to pull the candidate rows into
# Python to run the comparator. Cap how many we'll fetch from SQL so a wide
# filter (e.g. just name='glibc') can't run us out of memory if the fleet is
# unexpectedly large. A version filter on top of 50k candidate rows still
# completes in milliseconds, but holding 50k pydantic models in memory at
# once is excessive.
_VERSION_FILTER_CANDIDATE_CAP = 50_000

logger = logging.getLogger(__name__)

# Constant for the snapshot facet column. Lives here (and not as an enum on
# the model) because it's the join point between collectors and persistence
# — collectors decide which facet they ARE; persistence decides which facet
# row to upsert.
FACET_PACKAGES = "packages"


async def refresh_packages(
    db: AsyncSession,
    client: SaltAPIClient,
    *,
    target: str = "*",
    target_type: str = "glob",
    salt_jid: str | None = None,
) -> dict[str, int]:
    """Run the package collector and persist the results.

    Returns ``{minion_id: package_count}`` for every minion that responded
    and produced a non-empty snapshot. Minions that didn't respond are
    silently omitted — they retain whatever snapshot they had before.
    """
    results = await collect_packages(client, target=target, target_type=target_type)
    counts: dict[str, int] = {}
    for r in results:
        r.salt_jid = salt_jid
        await _persist_package_snapshot(db, r)
        counts[r.minion_id] = len(r.packages)
    await db.commit()
    logger.info(
        "inventory: refreshed packages for %d minion(s) (target=%r type=%s)",
        len(counts),
        target,
        target_type,
    )
    return counts


async def search_packages(db: AsyncSession, q: PackageQueryIn) -> PackageQueryOut:
    """Run a structured package query against the inventory.

    SQL handles the cheap, indexed predicates (``name``, ``source``,
    ``minion_id``, pagination). Version comparison runs in Python after
    SQL narrows the candidate set, because ``version`` is a free-text
    string whose ordering depends on the row's ``source`` (apt vs rpm vs
    pacman vs generic).

    The total returned is the *unfiltered* SQL row count when no version
    filter is present, or the count of rows that passed the Python
    comparator. ``truncated`` is True when the SQL set was capped before
    the comparator could see every candidate.
    """
    stmt = select(InventoryPackage)

    if q.name is not None:
        if q.name.op == "eq":
            stmt = stmt.where(InventoryPackage.name == q.name.value)
        elif q.name.op == "prefix":
            # NB: % and _ are SQL LIKE wildcards. The frontend should never
            # send those, but escape defensively so a user typing "lib%foo"
            # in the search box doesn't accidentally match more than they
            # intended.
            escaped = _escape_like(q.name.value)
            stmt = stmt.where(InventoryPackage.name.like(escaped + "%", escape="\\"))
        else:  # contains
            escaped = _escape_like(q.name.value)
            stmt = stmt.where(InventoryPackage.name.like("%" + escaped + "%", escape="\\"))

    if q.source is not None:
        stmt = stmt.where(InventoryPackage.source == q.source)

    if q.minion_id:
        stmt = stmt.where(InventoryPackage.minion_id == q.minion_id)

    # Stable order — primarily by minion, then package name. Predictable for
    # pagination and pleasant in the UI.
    stmt = stmt.order_by(InventoryPackage.minion_id, InventoryPackage.name)

    if q.version is None:
        # Cheap path: SQL alone is authoritative. Use a windowed query for
        # total + page.
        total_stmt = select(func.count()).select_from(stmt.subquery())
        total = int((await db.execute(total_stmt)).scalar() or 0)
        page = stmt.limit(q.limit).offset(q.offset)
        rows = (await db.execute(page)).scalars().all()
        return PackageQueryOut(
            total=total,
            hits=[_row_to_hit(r) for r in rows],
        )

    # Expensive path: pull up to _VERSION_FILTER_CANDIDATE_CAP rows and
    # filter in Python.
    candidates_stmt = stmt.limit(_VERSION_FILTER_CANDIDATE_CAP)
    candidates = (await db.execute(candidates_stmt)).scalars().all()
    truncated = len(candidates) >= _VERSION_FILTER_CANDIDATE_CAP

    matched: list[InventoryPackage] = [
        row
        for row in candidates
        if satisfies(row.version, q.version.op, q.version.value, row.source)
    ]
    total = len(matched)
    sliced = matched[q.offset : q.offset + q.limit]
    return PackageQueryOut(
        total=total,
        hits=[_row_to_hit(r) for r in sliced],
        truncated=truncated,
    )


def _row_to_hit(row: InventoryPackage) -> PackageQueryHit:
    return PackageQueryHit(
        minion_id=row.minion_id,
        name=row.name,
        version=row.version,
        arch=row.arch,
        source=row.source,
        collected_at=row.collected_at,
    )


async def aggregate_packages(
    db: AsyncSession,
    *,
    name_query: str | None = None,
    source: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> PackageAggregateOut:
    """Return the fleet-wide package list, one row per package name.

    This is the *default landing view* for the inventory UI — no filter is
    required, so the user sees what's there immediately. The query is a
    GROUP BY name with two distinct counts and one max; with the
    ``ix_inventory_pkg_name`` index Postgres satisfies it via an index-only
    aggregate. Even at 3-digit fleet × thousands-of-packages scale it
    completes in milliseconds.

    ``name_query`` does a case-insensitive substring match — deliberately
    fuzzy because users typing into the search box rarely remember whether
    the package is ``openssh-server`` or ``openssh-clients``.
    """
    base = select(InventoryPackage)
    if name_query:
        # Case-insensitive substring. We escape LIKE wildcards in the user
        # input for the same reason as in search_packages.
        escaped = _escape_like(name_query)
        base = base.where(InventoryPackage.name.ilike(f"%{escaped}%", escape="\\"))
    if source:
        base = base.where(InventoryPackage.source == source)
    base_subq = base.subquery()

    # Count of distinct names matching the filter (for pagination metadata).
    total_stmt = select(func.count(distinct(base_subq.c.name)))
    total = int((await db.execute(total_stmt)).scalar() or 0)

    grouped_stmt = (
        select(
            base_subq.c.name.label("name"),
            func.count(distinct(base_subq.c.minion_id)).label("minion_count"),
            func.count(distinct(base_subq.c.version)).label("version_count"),
            func.max(base_subq.c.collected_at).label("last_seen"),
        )
        .group_by(base_subq.c.name)
        .order_by(base_subq.c.name)
        .limit(limit)
        .offset(offset)
    )
    rows = (await db.execute(grouped_stmt)).all()

    return PackageAggregateOut(
        total=total,
        items=[
            PackageAggregate(
                name=row.name,
                minion_count=int(row.minion_count),
                version_count=int(row.version_count),
                last_seen=row.last_seen,
            )
            for row in rows
        ],
    )


async def aggregate_versions(
    db: AsyncSession,
    *,
    name: str,
    source: str | None = None,
) -> VersionAggregateOut:
    """Return one row per distinct (version, arch, source) for the given package.

    Used by the level-2 view ("click a package name → see all versions").
    Sorted by minion_count desc so the dominant version sits at the top
    — that's typically what an operator wants to know first ("how many
    boxes are on the current vs. older releases").
    """
    stmt = (
        select(
            InventoryPackage.version.label("version"),
            InventoryPackage.arch.label("arch"),
            InventoryPackage.source.label("source"),
            func.count(distinct(InventoryPackage.minion_id)).label("minion_count"),
        )
        .where(InventoryPackage.name == name)
        .group_by(
            InventoryPackage.version,
            InventoryPackage.arch,
            InventoryPackage.source,
        )
    )
    if source:
        stmt = stmt.where(InventoryPackage.source == source)
    # Dominant version first; tiebreak by version string for stable ordering.
    stmt = stmt.order_by(
        func.count(distinct(InventoryPackage.minion_id)).desc(),
        InventoryPackage.version,
    )
    rows = (await db.execute(stmt)).all()
    items = [
        VersionAggregate(
            version=row.version,
            arch=row.arch,
            source=row.source,
            minion_count=int(row.minion_count),
        )
        for row in rows
    ]
    return VersionAggregateOut(name=name, total=len(items), items=items)


def _escape_like(value: str) -> str:
    """Escape SQL LIKE wildcards. Pair with ``escape='\\\\'`` on the .like()."""
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


async def _persist_package_snapshot(db: AsyncSession, r: CollectorResult) -> None:
    """Replace this minion's rows in ``inventory_package`` and upsert the
    snapshot row. Caller owns the transaction (we don't commit here)."""
    # 1. Wipe the minion's old rows so we don't end up with stale packages
    #    after uninstalls.
    _ = await db.execute(delete(InventoryPackage).where(InventoryPackage.minion_id == r.minion_id))

    # 2. Bulk-insert the fresh data. Salt has been observed (rarely) to
    #    return duplicate (name, arch) pairs when a host has multiple
    #    repositories shipping the same package; dedupe defensively so we
    #    don't trip the uniqueness constraint and roll back the whole batch.
    deduped: dict[tuple[str, str | None], tuple[str, str, str | None]] = {}
    for entry in r.packages:
        deduped[(entry.name, entry.arch)] = (entry.name, entry.version, entry.arch)
    if deduped:
        db.add_all(
            InventoryPackage(
                minion_id=r.minion_id,
                name=name,
                version=version,
                arch=arch,
                source=r.source,
                collected_at=r.collected_at,
            )
            for name, version, arch in deduped.values()
        )

    # 3. Upsert the snapshot row. We do this last so item_count reflects the
    #    deduped insert count.
    existing = (
        await db.execute(
            select(InventorySnapshot).where(
                InventorySnapshot.minion_id == r.minion_id,
                InventorySnapshot.facet == FACET_PACKAGES,
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        existing.collected_at = r.collected_at
        existing.salt_jid = r.salt_jid
        existing.item_count = len(deduped)
    else:
        db.add(
            InventorySnapshot(
                minion_id=r.minion_id,
                facet=FACET_PACKAGES,
                collected_at=r.collected_at,
                salt_jid=r.salt_jid,
                item_count=len(deduped),
            )
        )
