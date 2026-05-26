# backend/src/halite/salt_docs/routes.py
from __future__ import annotations

from fastapi import APIRouter, Request

from halite.deps import CurrentUser
from halite.salt.client import SaltAPIError, SaltAPIUnavailable
from halite.salt.deps import salt_client_or_503, wrap_salt_errors
from halite.salt_docs.schemas import SaltFunctionsOut
from halite.salt_docs.service import get_functions

router = APIRouter(prefix="/api/salt", tags=["salt-docs"])


@router.get(
    "/functions",
    response_model=SaltFunctionsOut,
)
async def list_functions_route(
    request: Request,
    _actor: CurrentUser,
) -> SaltFunctionsOut:
    """List the names of execution functions the salt master knows about.

    Requires authentication (any logged-in user). Cached for 1 hour to
    avoid hammering salt-api on every page render.
    """
    client = salt_client_or_503(request)
    try:
        functions, cached_at = await get_functions(client)
    except (SaltAPIUnavailable, SaltAPIError) as exc:
        raise wrap_salt_errors(exc) from None
    return SaltFunctionsOut(functions=functions, cached_at=cached_at)
