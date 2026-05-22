# backend/src/halite/salt/deps.py
"""Route helpers for salt-backed FastAPI routers."""
from __future__ import annotations

from fastapi import HTTPException, Request, status

from halite.salt.client import SaltAPIClient, SaltAPIError, SaltAPIUnavailable


def salt_client_or_503(request: Request) -> SaltAPIClient:
    """Return the configured SaltAPIClient, or raise 503 if Salt-API is not configured."""
    client = getattr(request.app.state, "salt_client", None)
    if client is None:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Salt-API is not configured. Set SALT_API_URL, SALT_API_USERNAME, SALT_API_PASSWORD.",
        )
    return client


def wrap_salt_errors(exc: Exception) -> HTTPException:
    """Translate SaltAPI* exceptions into HTTPException. Re-raises unknown types."""
    if isinstance(exc, SaltAPIUnavailable):
        return HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, f"Salt-API unreachable: {exc}"
        )
    if isinstance(exc, SaltAPIError):
        return HTTPException(
            status.HTTP_502_BAD_GATEWAY, f"Salt-API error {exc.status}: {exc}"
        )
    raise exc
