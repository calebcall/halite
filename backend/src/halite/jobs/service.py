# backend/src/halite/jobs/service.py
from __future__ import annotations

import contextlib
from datetime import UTC, datetime, timedelta
from typing import Any

from halite.jobs.schemas import (
    JobActivityBucket,
    JobActivityOut,
    JobDetail,
    JobMinionResult,
    JobSummary,
)
from halite.salt.client import SaltAPIClient, SaltAPIError, SaltAPIUnavailable


def _summary_from_raw(jid: str, raw: dict[str, Any], *, is_active: bool) -> JobSummary:
    return JobSummary(
        jid=jid,
        function=str(raw.get("Function") or ""),
        target=str(raw.get("Target") or ""),
        target_type=_opt_str(raw.get("Target-type")),
        user=_opt_str(raw.get("User")),
        start_time=_opt_str(raw.get("StartTime")),
        status="running" if is_active else "complete",
    )


def _opt_str(value: Any) -> str | None:
    if value is None or value == "":
        return None
    return str(value)


def _split_args_and_kwargs(raw_args: list[Any]) -> tuple[list[Any], dict[str, Any]]:
    """Salt embeds kwargs as the trailing dict entry with __kwarg__: True.
    Returns (positional_args, kwargs). If no kwarg entry, kwargs is empty."""
    if raw_args and isinstance(raw_args[-1], dict) and raw_args[-1].get("__kwarg__") is True:
        kwarg_entry = dict(raw_args[-1])
        kwarg_entry.pop("__kwarg__", None)
        return list(raw_args[:-1]), kwarg_entry
    return list(raw_args), {}


async def list_recent_jobs(client: SaltAPIClient, *, limit: int) -> list[JobSummary]:
    raw = await client.list_jobs(limit=limit)
    active: set[str] = set()
    # If the active call fails for any reason, default every job to
    # complete. We don't want a salt-api hiccup to take down the
    # entire Jobs list view.
    with contextlib.suppress(SaltAPIError, SaltAPIUnavailable):
        active = set((await client.list_active_jobs()).keys())
    return [
        _summary_from_raw(jid, j, is_active=jid in active)
        for jid, j in raw.items()
    ]


async def get_job_detail(client: SaltAPIClient, jid: str) -> JobDetail | None:
    raw = await client.get_job(jid)
    if raw is None:
        return None
    results_raw = raw.get("Result") or {}
    minions = list(raw.get("Minions") or [])
    if not minions and isinstance(results_raw, dict):
        minions = list(results_raw.keys())
    results: list[JobMinionResult] = []
    if isinstance(results_raw, dict):
        for minion_id, value in results_raw.items():
            if isinstance(value, dict):
                results.append(JobMinionResult(
                    minion=str(minion_id),
                    success=_opt_bool(value.get("success")),
                    retcode=_opt_int(value.get("retcode")),
                    return_value=value.get("return"),
                ))
            else:
                results.append(JobMinionResult(
                    minion=str(minion_id),
                    return_value=value,
                ))
    positional, kwargs = _split_args_and_kwargs(list(raw.get("Arguments") or []))
    return JobDetail(
        jid=jid,
        function=str(raw.get("Function") or ""),
        arguments=positional,
        kwargs=kwargs,
        target=str(raw.get("Target") or ""),
        target_type=_opt_str(raw.get("Target-type")),
        user=_opt_str(raw.get("User")),
        start_time=_opt_str(raw.get("StartTime")),
        minions=minions,
        results=results,
    )


def _jid_to_utc(jid: str) -> datetime | None:
    """Parse a Salt JID (``YYYYMMDDHHMMSSffffff``, UTC) into a datetime.
    Returns None for non-JID-shaped keys so aggregation can skip them
    rather than 500-ing on stray cache entries.
    """
    if len(jid) != 20 or not jid.isdigit():
        return None
    try:
        return datetime(
            year=int(jid[0:4]),
            month=int(jid[4:6]),
            day=int(jid[6:8]),
            hour=int(jid[8:10]),
            minute=int(jid[10:12]),
            second=int(jid[12:14]),
            microsecond=int(jid[14:20]),
            tzinfo=UTC,
        )
    except ValueError:
        return None


async def get_job_activity(client: SaltAPIClient, *, hours: int) -> JobActivityOut:
    """Aggregate the master's job cache into per-hour buckets.

    Uses ``runner.jobs.list_jobs`` directly (no limit slice) and buckets by
    JID-derived UTC timestamp. ``running`` is independent of the window —
    jobs that started before the window but are still executing still count.
    Falls back to ``running=0`` if ``jobs.active`` fails.
    """
    raw = await client.runner_call("jobs.list_jobs")
    if not isinstance(raw, dict):
        raw = {}

    # Snap "now" to the top of the current hour so the X-axis is stable
    # within a single hour and identical buckets line up across consecutive
    # polls (the chart doesn't shift sideways every 30s).
    now = datetime.now(UTC).replace(minute=0, second=0, microsecond=0)
    window_start = now - timedelta(hours=hours - 1)
    counts = [0] * hours
    for jid in raw:
        ts = _jid_to_utc(str(jid))
        if ts is None:
            continue
        if ts < window_start or ts >= now + timedelta(hours=1):
            continue
        idx = int((ts - window_start).total_seconds() // 3600)
        if 0 <= idx < hours:
            counts[idx] += 1

    buckets = [
        JobActivityBucket(
            hour_start=(window_start + timedelta(hours=i))
                .strftime("%Y-%m-%dT%H:%M:%SZ"),
            count=counts[i],
        )
        for i in range(hours)
    ]

    running = 0
    with contextlib.suppress(SaltAPIError, SaltAPIUnavailable):
        active = await client.list_active_jobs()
        running = len(active)

    return JobActivityOut(
        hours=hours,
        buckets=buckets,
        total=sum(counts),
        running=running,
    )


def _opt_bool(value: Any) -> bool | None:
    if value is None:
        return None
    return bool(value)


def _opt_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
