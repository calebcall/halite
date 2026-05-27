from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from halite.fleet.models import HighstateRun
from halite.jobs.index_model import JobIndexEntry
from halite.jobs.timeline_schemas import (
    TimelineBar,
    TimelineCategory,
    TimelineGroup,
    TimelineGroupBy,
    TimelineOut,
    TimelineWindow,
)

_WINDOW_TO_DELTA: dict[TimelineWindow, timedelta] = {
    "1h": timedelta(hours=1),
    "4h": timedelta(hours=4),
    "24h": timedelta(hours=24),
    "7d": timedelta(days=7),
}


_CATEGORY_BY_PREFIX: dict[str, TimelineCategory] = {
    "cmd": "cmd",
    "manage": "manage",
    "pkg": "pkg",
    "runner": "runner",
    "service": "service",
    "state": "state",
    "test": "test",
    "wheel": "wheel",
}

_STATE_PREFIXES = ("state.",)
_SYSTEM_PREFIXES = ("runner.", "wheel.", "manage.")


def _category_for(function: str) -> TimelineCategory:
    if "." in function:
        head = function.split(".", 1)[0]
        return _CATEGORY_BY_PREFIX.get(head, "other")
    return "other"


def _anchor_utc(d: datetime) -> datetime:
    return d if d.tzinfo is not None else d.replace(tzinfo=UTC)


async def get_timeline(
    db: AsyncSession,
    *,
    window: TimelineWindow,
    group_by: TimelineGroupBy,
    include_system: bool,
    function_filter: str | None,
    user_filter: str | None,
    active_jids: set[str] | None,
    active_jids_refreshed_at: datetime | None,
    max_bars: int = 2000,
) -> TimelineOut:
    """Aggregate jobs_index + highstate_runs into ready-to-render groups.

    Caps total bars at ``max_bars`` to keep the SVG render bounded —
    plotting 36k bars in the DOM is a guaranteed jank. We retain the
    most-recent rows when capping.
    """
    now = datetime.now(tz=UTC)
    window_start = now - _WINDOW_TO_DELTA[window]

    # ----- query jobs in window -----
    stmt = (
        select(JobIndexEntry)
        .where(JobIndexEntry.started_at >= window_start)
        .order_by(JobIndexEntry.started_at.desc())
        .limit(max_bars)
    )
    if not include_system:
        # Avoid the noisy background traffic from Halite's own pollers.
        for pre in _SYSTEM_PREFIXES:
            stmt = stmt.where(~JobIndexEntry.function.startswith(pre))
    if function_filter:
        stmt = stmt.where(JobIndexEntry.function.ilike(f"%{function_filter}%"))
    if user_filter:
        stmt = stmt.where(JobIndexEntry.user == user_filter)

    rows = (await db.execute(stmt)).scalars().all()

    # ----- aggregate highstate completion + failures per state job jid -----
    state_jids = [r.jid for r in rows if r.function.startswith(_STATE_PREFIXES)]
    state_agg: dict[str, dict] = {}
    if state_jids:
        agg_stmt = (
            select(
                HighstateRun.jid,
                func.max(HighstateRun.completed_at).label("max_completed"),
                func.count(HighstateRun.id).label("minion_count"),
                func.sum(HighstateRun.fail_count).label("fail_count_total"),
                func.sum(HighstateRun.change_count).label("change_count_total"),
                func.count(
                    func.nullif(HighstateRun.fail_count, 0)
                ).label("failed_minion_count"),
            )
            .where(HighstateRun.jid.in_(state_jids))
            .group_by(HighstateRun.jid)
        )
        for agg in (await db.execute(agg_stmt)).all():
            state_agg[agg.jid] = {
                "change_total": int(agg.change_count_total or 0),
                "fail_total": int(agg.fail_count_total or 0),
                "failed_minions": int(agg.failed_minion_count or 0),
                "max_completed": agg.max_completed,
                "minion_count": int(agg.minion_count or 0),
            }

    # ----- build bars -----
    bars_by_group: dict[str, list[TimelineBar]] = {}
    group_meta: dict[str, tuple[str, TimelineCategory]] = {}
    total = 0
    for r in rows:
        category = _category_for(r.function)
        is_state = r.function.startswith(_STATE_PREFIXES)
        agg = state_agg.get(r.jid)

        # Status derivation
        if active_jids is not None and r.jid in active_jids:
            status = "running"
            completed_at: datetime | None = None
        elif is_state and agg:
            if agg["fail_total"] > 0:
                status = "failed"
            elif agg["change_total"] > 0:
                status = "changed"
            else:
                status = "pass"
            completed_at = agg["max_completed"]
            if completed_at is not None:
                completed_at = _anchor_utc(completed_at)
        elif is_state:
            # state job, but we haven't ingested its result yet
            status = "unknown"
            completed_at = None
        else:
            # non-state job, no completion timestamp available
            status = "pass"  # treat as complete
            completed_at = None

        bar = TimelineBar(
            category=category,
            completed_at=completed_at,
            failed_minion_count=agg["failed_minions"] if agg else None,
            function=r.function,
            jid=r.jid,
            minion_count=agg["minion_count"] if agg else None,
            started_at=_anchor_utc(r.started_at),
            status=status,
            target=r.target,
            user=r.user,
        )

        if group_by == "function":
            key = r.function
            label = r.function
        else:  # user
            key = r.user or "<unknown>"
            label = r.user or "(no user)"

        bars_by_group.setdefault(key, []).append(bar)
        group_meta.setdefault(key, (label, category))
        total += 1

    # Sort groups: by bar count desc (busiest first); ties by key asc.
    groups = [
        TimelineGroup(
            bar_count=len(bars),
            bars=bars,
            category=group_meta[key][1],
            key=key,
            label=group_meta[key][0],
        )
        for key, bars in bars_by_group.items()
    ]
    groups.sort(key=lambda g: (-g.bar_count, g.key))

    return TimelineOut(
        active_known=active_jids is not None,
        group_by=group_by,
        groups=groups,
        last_polled_at=active_jids_refreshed_at,
        total_bars=total,
        window_end=now,
        window_start=window_start,
    )
