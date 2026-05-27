from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, HTTPException, Request, status

from halite.db import SessionDep
from halite.deps import CurrentUser
from halite.fleet.schemas import (
    ComplianceSeriesOut,
    FleetHealthOut,
    RunDetailOut,
    TopFailuresOut,
)
from halite.fleet.service import (
    compliance_series,
    fleet_health,
    get_run,
    latest_per_minion,
    top_failures,
)

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/fleet", tags=["fleet"])


@router.get("/health", response_model=FleetHealthOut)
async def fleet_health_route(
    request: Request, db: SessionDep, _: CurrentUser
) -> FleetHealthOut:
    scheduler = getattr(request.app.state, "fleet_scheduler", None)
    cached_connected = (
        scheduler.connected_minions if scheduler is not None else None
    )
    if cached_connected is not None:
        connected = cached_connected
    else:
        # Cold-start fallback: scheduler hasn't ticked yet. Use the set
        # of minions we have runs for; they'll all appear "online" until
        # the first connectivity refresh. Better than blocking on a
        # slow live salt call.
        runs = await latest_per_minion(db)
        connected = {r.minion_id for r in runs}
    minions = await fleet_health(db, connected=connected)
    return FleetHealthOut(total_minions=len(minions), minions=minions)


@router.get("/compliance", response_model=ComplianceSeriesOut)
async def compliance_route(
    db: SessionDep, _: CurrentUser, limit: int = 30
) -> ComplianceSeriesOut:
    limit = max(1, min(limit, 200))
    buckets = await compliance_series(db, limit=limit)
    return ComplianceSeriesOut(buckets=buckets)


@router.get("/top-failures", response_model=TopFailuresOut)
async def top_failures_route(
    db: SessionDep, _: CurrentUser, limit: int = 10
) -> TopFailuresOut:
    limit = max(1, min(limit, 50))
    failures = await top_failures(db, limit=limit)
    return TopFailuresOut(failures=failures)


@router.get("/runs/{run_id}", response_model=RunDetailOut)
async def run_detail_route(
    run_id: uuid.UUID, db: SessionDep, _: CurrentUser
) -> RunDetailOut:
    run = await get_run(db, run_id)
    if run is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Run not found")
    return RunDetailOut.model_validate(run)
