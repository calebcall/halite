# backend/src/halite/jobs/routes.py
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request, Response, status

from halite.audit.writer import record as audit_record
from halite.db import SessionDep
from halite.deps import CurrentUser, require_perm
from halite.jobs.schemas import JobActivityOut, JobDetail, JobsListOut
from halite.jobs.service import get_job_activity, get_job_detail, list_recent_jobs
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
    "/activity",
    response_model=JobActivityOut,
    dependencies=[require_perm("view", "job:*")],
)
async def jobs_activity_route(
    request: Request,
    # Cap at 168 (7 days). Beyond that the cache is usually pruned and the
    # client-side chart starts to chart mostly empty buckets.
    hours: int = Query(default=24, ge=1, le=168),
) -> JobActivityOut:
    client = salt_client_or_503(request)
    try:
        return await get_job_activity(client, hours=hours)
    except (SaltAPIUnavailable, SaltAPIError) as exc:
        raise wrap_salt_errors(exc) from None


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


@router.post(
    "/{jid}/kill",
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[require_perm("kill", "job:*")],
)
async def kill_job_route(
    jid: str,
    request: Request,
    db: SessionDep,
    actor: CurrentUser,
) -> Response:
    client = salt_client_or_503(request)
    try:
        await client.kill_job(jid)
    except (SaltAPIUnavailable, SaltAPIError) as exc:
        http_exc = wrap_salt_errors(exc)
        await audit_record(
            db, user_id=actor.id, action="job.kill",
            resource=f"job:{jid}", args_json=None, salt_jid=jid,
            decision="deny", result_code=http_exc.status_code,
        )
        await db.commit()
        raise http_exc from None
    await audit_record(
        db, user_id=actor.id, action="job.kill",
        resource=f"job:{jid}", args_json=None, salt_jid=jid,
        decision="allow", result_code=202,
    )
    await db.commit()
    return Response(status_code=status.HTTP_202_ACCEPTED)
