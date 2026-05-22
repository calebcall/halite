# backend/src/halite/jobs/service.py
from __future__ import annotations

from typing import Any

from halite.jobs.schemas import JobDetail, JobMinionResult, JobSummary
from halite.salt.client import SaltAPIClient


def _summary_from_raw(jid: str, raw: dict[str, Any]) -> JobSummary:
    return JobSummary(
        jid=jid,
        function=str(raw.get("Function") or ""),
        target=str(raw.get("Target") or ""),
        target_type=_opt_str(raw.get("Target-type")),
        user=_opt_str(raw.get("User")),
        start_time=_opt_str(raw.get("StartTime")),
    )


def _opt_str(value: Any) -> str | None:
    if value is None or value == "":
        return None
    return str(value)


async def list_recent_jobs(client: SaltAPIClient, *, limit: int) -> list[JobSummary]:
    raw = await client.list_jobs(limit=limit)
    return [_summary_from_raw(jid, j) for jid, j in raw.items()]


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
    return JobDetail(
        jid=jid,
        function=str(raw.get("Function") or ""),
        arguments=list(raw.get("Arguments") or []),
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
