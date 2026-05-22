# backend/src/halite/minions/routes.py
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, status

from halite.deps import require_perm
from halite.minions.schemas import MinionDetail, MinionListOut
from halite.minions.service import get_minion_detail, list_minions_with_status
from halite.salt.client import SaltAPIError, SaltAPIUnavailable

router = APIRouter(prefix="/api/minions", tags=["minions"])


def _salt_client_or_503(request: Request):
    client = getattr(request.app.state, "salt_client", None)
    if client is None:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Salt-API is not configured. Set SALT_API_URL, SALT_API_USERNAME, SALT_API_PASSWORD.",
        )
    return client


def _wrap_salt_errors(exc: Exception) -> HTTPException:
    if isinstance(exc, SaltAPIUnavailable):
        return HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, f"Salt-API unreachable: {exc}"
        )
    if isinstance(exc, SaltAPIError):
        return HTTPException(
            status.HTTP_502_BAD_GATEWAY, f"Salt-API error {exc.status}: {exc}"
        )
    raise exc


@router.get(
    "",
    response_model=MinionListOut,
    dependencies=[require_perm("view", "minion:*")],
)
async def list_minions_route(request: Request) -> MinionListOut:
    client = _salt_client_or_503(request)
    try:
        minions = await list_minions_with_status(client)
    except (SaltAPIUnavailable, SaltAPIError) as exc:
        raise _wrap_salt_errors(exc) from None
    return MinionListOut(total=len(minions), minions=minions)


@router.get(
    "/{minion_id}",
    response_model=MinionDetail,
    dependencies=[require_perm("view", "minion:*")],
)
async def get_minion_route(minion_id: str, request: Request) -> MinionDetail:
    client = _salt_client_or_503(request)
    try:
        detail = await get_minion_detail(client, minion_id)
    except (SaltAPIUnavailable, SaltAPIError) as exc:
        raise _wrap_salt_errors(exc) from None
    if detail is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Minion not found")
    return detail
