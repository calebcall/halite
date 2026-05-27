# backend/src/halite/jobs/routes.py
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request, Response, status

from halite.audit.writer import record as audit_record
from halite.db import SessionDep
from halite.deps import CurrentUser, require_perm
from halite.jobs.index_service import (
    get_activity_from_db,
    list_recent_jobs_from_db,
)
from halite.jobs.schemas import JobActivityOut, JobDetail, JobsListOut
from halite.jobs.service import get_job_detail, list_recent_jobs
from halite.jobs.timeline_schemas import TimelineOut
from halite.jobs.timeline_service import get_timeline
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
    db: SessionDep,
    limit: int = Query(default=50, ge=1, le=500),
    live: bool = Query(default=False),
) -> JobsListOut:
    if live:
        # Authoritative master view — power-user escape hatch when the
        # operator just kicked off a job and the poller hasn't ticked.
        client = salt_client_or_503(request)
        try:
            jobs = await list_recent_jobs(client, limit=limit)
        except (SaltAPIUnavailable, SaltAPIError) as exc:
            raise wrap_salt_errors(exc) from None
        return JobsListOut(total=len(jobs), jobs=jobs)
    runtime = request.app.state.runtime
    return await list_recent_jobs_from_db(
        db,
        limit=limit,
        active_jids=runtime.active_jids,
        last_polled_at=runtime.active_jids_refreshed_at,
    )


@router.get(
    "/activity",
    response_model=JobActivityOut,
    dependencies=[require_perm("view", "job:*")],
)
async def jobs_activity_route(
    request: Request,
    db: SessionDep,
    # Cap at 168 (7 days). Beyond that the cache is usually pruned and the
    # client-side chart starts to chart mostly empty buckets.
    hours: int = Query(default=24, ge=1, le=168),
) -> JobActivityOut:
    runtime = request.app.state.runtime
    return await get_activity_from_db(
        db,
        hours=hours,
        active_jids=runtime.active_jids,
        last_polled_at=runtime.active_jids_refreshed_at,
    )


@router.get(
    "/timeline",
    response_model=TimelineOut,
    dependencies=[require_perm("view", "job:*")],
)
async def jobs_timeline_route(
    request: Request,
    db: SessionDep,
    window: str = Query(default="24h"),
    group_by: str = Query(default="function"),
    include_system: bool = Query(default=False),
    function_filter: str | None = Query(default=None, max_length=128),
    user: str | None = Query(default=None, max_length=255),
) -> TimelineOut:
    if window not in {"1h", "4h", "24h", "7d"}:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Invalid window")
    if group_by not in {"function", "user"}:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Invalid group_by")
    runtime = request.app.state.runtime
    return await get_timeline(
        db,
        window=window,  # type: ignore[arg-type]
        group_by=group_by,  # type: ignore[arg-type]
        include_system=include_system,
        function_filter=function_filter,
        user_filter=user,
        active_jids=runtime.active_jids,
        active_jids_refreshed_at=runtime.active_jids_refreshed_at,
    )


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
