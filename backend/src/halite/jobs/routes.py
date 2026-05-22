# backend/src/halite/jobs/routes.py
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request, status

from halite.deps import require_perm
from halite.jobs.schemas import JobDetail, JobsListOut
from halite.jobs.service import get_job_detail, list_recent_jobs
from halite.salt.client import SaltAPIError, SaltAPIUnavailable
from halite.salt.deps import salt_client_or_503, wrap_salt_errors

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


@router.get(
    "",
    response_model=JobsListOut,
    dependencies=[require_perm("view", "job:*")],
)
async def list_jobs_route(
    request: Request,
    limit: int = Query(default=50, ge=1, le=500),
) -> JobsListOut:
    client = salt_client_or_503(request)
    try:
        jobs = await list_recent_jobs(client, limit=limit)
    except (SaltAPIUnavailable, SaltAPIError) as exc:
        raise wrap_salt_errors(exc) from None
    return JobsListOut(total=len(jobs), jobs=jobs)


@router.get(
    "/{jid}",
    response_model=JobDetail,
    dependencies=[require_perm("view", "job:*")],
)
async def get_job_route(jid: str, request: Request) -> JobDetail:
    client = salt_client_or_503(request)
    try:
        detail = await get_job_detail(client, jid)
    except (SaltAPIUnavailable, SaltAPIError) as exc:
        raise wrap_salt_errors(exc) from None
    if detail is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Job {jid} not found in cache")
    return detail
