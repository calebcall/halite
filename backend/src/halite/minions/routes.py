# backend/src/halite/minions/routes.py
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, status

from halite.deps import require_perm
from halite.minions.schemas import MinionDetail, MinionListOut
from halite.minions.service import get_minion_detail, list_minions_with_status
from halite.salt.client import SaltAPIError, SaltAPIUnavailable
from halite.salt.deps import salt_client_or_503, wrap_salt_errors

router = APIRouter(prefix="/api/minions", tags=["minions"])


@router.get(
    "",
    response_model=MinionListOut,
    dependencies=[require_perm("view", "minion:*")],
)
async def list_minions_route(request: Request) -> MinionListOut:
    client = salt_client_or_503(request)
    try:
        minions = await list_minions_with_status(client)
    except (SaltAPIUnavailable, SaltAPIError) as exc:
        raise wrap_salt_errors(exc) from None
    return MinionListOut(total=len(minions), minions=minions)


@router.get(
    "/{minion_id}",
    response_model=MinionDetail,
    dependencies=[require_perm("view", "minion:*")],
)
async def get_minion_route(minion_id: str, request: Request) -> MinionDetail:
    client = salt_client_or_503(request)
    try:
        detail = await get_minion_detail(client, minion_id)
    except (SaltAPIUnavailable, SaltAPIError) as exc:
        raise wrap_salt_errors(exc) from None
    if detail is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Minion not found")
    return detail
