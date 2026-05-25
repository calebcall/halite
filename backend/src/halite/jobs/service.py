# backend/src/halite/jobs/service.py
from __future__ import annotations

import contextlib
from typing import Any

from halite.jobs.schemas import JobDetail, JobMinionResult, JobSummary
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
