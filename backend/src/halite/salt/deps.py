# backend/src/halite/salt/deps.py
"""Route helpers for salt-backed FastAPI routers."""
from __future__ import annotations

import re

from fastapi import HTTPException, Request, status

from halite.salt.client import SaltAPIClient, SaltAPIError, SaltAPIUnavailable

# Matches the first <p>...</p> in a CherryPy error page. DOTALL so the
# message can span lines.
_HTML_P_RE = re.compile(r"<p[^>]*>(.*?)</p>", re.DOTALL | re.IGNORECASE)
_TAG_RE = re.compile(r"<[^>]+>")
_MAX_MSG_LEN = 500


def _extract_salt_message(body: object) -> str | None:
    """Best-effort: pull a salt-side error message from CherryPy HTML or
    JSON-shaped body. Returns None if nothing usable is found."""
    if isinstance(body, dict):
        for key in ("detail", "message", "error"):
            v = body.get(key)
            if isinstance(v, str) and v.strip():
                return v.strip()[:_MAX_MSG_LEN]
        return None
    if isinstance(body, str) and body.strip():
        match = _HTML_P_RE.search(body)
        if match:
            text = _TAG_RE.sub("", match.group(1))
            text = " ".join(text.split())
            if text:
                return text[:_MAX_MSG_LEN]
    return None


def salt_client_or_503(request: Request) -> SaltAPIClient:
    """Return the live SaltAPIClient, or raise 503 if Salt-API is not configured.

    Reads from ``app.state.runtime.salt`` (RuntimeConfig) so the reference
    is always current after a hot-reload. Falls back to the legacy
    ``app.state.salt_client`` attribute for backward-compat with tests that
    set it directly.
    """
    runtime = getattr(request.app.state, "runtime", None)
    if runtime is not None:
        client = runtime.salt
    else:
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
            status.HTTP_503_SERVICE_UNAVAILABLE,
            f"Salt-API unreachable: {exc}",
        )
    if isinstance(exc, SaltAPIError):
        msg = _extract_salt_message(exc.body)
        detail = f"Salt-API error {exc.status}"
        if msg:
            detail = f"{detail}: {msg}"
        return HTTPException(status.HTTP_502_BAD_GATEWAY, detail)
    raise exc
