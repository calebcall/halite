from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from halite.audit.models import AuditEntry

_REDACTED = "[REDACTED]"
_SECRET_KEYS = frozenset(
    {
        "password",
        "passwd",
        "pw",
        "secret",
        "token",
        "api_key",
        "apikey",
        "authorization",
        "new_password",
        "current_password",
    }
)


def _redact(args: dict[str, Any] | None) -> dict[str, Any] | None:
    if args is None:
        return None
    out: dict[str, Any] = {}
    for k, v in args.items():
        if k.lower() in _SECRET_KEYS:
            out[k] = _REDACTED
        elif isinstance(v, dict):
            out[k] = _redact(v)
        else:
            out[k] = v
    return out


async def record(
    session: AsyncSession,
    *,
    user_id: uuid.UUID | None,
    action: str,
    resource: str,
    args_json: dict[str, Any] | None,
    salt_jid: str | None,
    decision: str,
    result_code: int,
    duration_ms: int = 0,
) -> None:
    entry = AuditEntry(
        at=datetime.now(tz=UTC),
        user_id=user_id,
        action=action,
        resource=resource,
        args_json=_redact(args_json),
        salt_jid=salt_jid,
        decision=decision,
        result_code=result_code,
        duration_ms=duration_ms,
    )
    session.add(entry)
