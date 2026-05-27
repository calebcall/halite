# backend/src/halite/minions/routes.py
from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from halite.db import SessionDep
from halite.deps import require_perm
from halite.minions.db_service import get_minion_from_db, list_minions_from_db
from halite.minions.schemas import MinionDetail, MinionListOut

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
