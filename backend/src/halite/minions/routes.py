# backend/src/halite/minions/routes.py
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, status

from halite.deps import require_perm
from halite.minions.schemas import MinionListOut
from halite.minions.service import list_minions
from halite.salt.client import SaltAPIError, SaltAPIUnavailable

router = APIRouter(prefix="/api/minions", tags=["minions"])


@router.get("", response_model=MinionListOut, dependencies=[require_perm("view", "minion:*")])
async def list_minions_route(request: Request) -> MinionListOut:
    salt_client = getattr(request.app.state, "salt_client", None)
    if salt_client is None:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Salt-API is not configured. Set SALT_API_URL, SALT_API_USERNAME, SALT_API_PASSWORD.",
        )
    try:
        minions = await list_minions(salt_client)
    except SaltAPIUnavailable as exc:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, f"Salt-API unreachable: {exc}"
        ) from None
    except SaltAPIError as exc:
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY, f"Salt-API error {exc.status}: {exc}"
        ) from None
    return MinionListOut(total=len(minions), minions=minions)
