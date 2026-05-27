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
from halite.salt.deps import salt_client_or_503

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/fleet", tags=["fleet"])


@router.get("/health", response_model=FleetHealthOut)
async def fleet_health_route(
    db: SessionDep, request: Request, _: CurrentUser
) -> FleetHealthOut:
    client = salt_client_or_503(request)
    try:
        connected_map = await client.list_connected_minions()
        connected = set(connected_map.keys())
    except Exception:
        log.exception("fleet_health: failed to fetch connectivity; treating known minions as online")
        # Fall back: trust whatever's in highstate_runs as the minion list,
        # assume they're online (we can't tell). The truly-offline ones
        # will look healthy during the outage — acceptable degrade.
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
