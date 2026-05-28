# backend/src/halite/minions/routes.py
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, status

from halite.db import SessionDep
from halite.deps import CurrentUser, require_perm
from halite.minions.db_service import get_minion_from_db, list_minions_from_db
from halite.minions.runs_service import list_compliance, list_runs
from halite.minions.schemas import (
    MinionComplianceOut,
    MinionDetail,
    MinionListOut,
    MinionRunsOut,
)

router = APIRouter(prefix="/api/minions", tags=["minions"])


@router.get(
    "",
    response_model=MinionListOut,
    dependencies=[require_perm("view", "minion:*")],
)
async def list_minions_route(db: SessionDep) -> MinionListOut:
    return await list_minions_from_db(db)


@router.get(
    "/{minion_id}",
    response_model=MinionDetail,
    dependencies=[require_perm("view", "minion:*")],
)
async def get_minion_route(minion_id: str, db: SessionDep) -> MinionDetail:
    out = await get_minion_from_db(db, minion_id)
    if out is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Minion not found")
    return out


@router.get(
    "/{minion_id}/runs",
    response_model=MinionRunsOut,
    dependencies=[require_perm("view", "minion:*")],
)
async def list_minion_runs_route(
    minion_id: str,
    db: SessionDep,
    _: CurrentUser,
    limit: int = Query(default=20, ge=1, le=200),
) -> MinionRunsOut:
    return await list_runs(db, minion_id, limit=limit)


@router.get(
    "/{minion_id}/compliance",
    response_model=MinionComplianceOut,
    dependencies=[require_perm("view", "minion:*")],
)
async def list_minion_compliance_route(
    minion_id: str,
    db: SessionDep,
    _: CurrentUser,
    limit: int = Query(default=30, ge=1, le=200),
) -> MinionComplianceOut:
    return await list_compliance(db, minion_id, limit=limit)
