# backend/src/halite/keys/routes.py
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, Response, status

from halite.audit.writer import record as audit_record
from halite.db import SessionDep
from halite.deps import CurrentUser, require_perm
from halite.keys.schemas import KeysListOut
from halite.keys.service import list_keys
from halite.salt.client import SaltAPIError, SaltAPIUnavailable

router = APIRouter(prefix="/api/keys", tags=["keys"])


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
        return HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, f"Salt-API unreachable: {exc}")
    if isinstance(exc, SaltAPIError):
        return HTTPException(status.HTTP_502_BAD_GATEWAY, f"Salt-API error {exc.status}: {exc}")
    raise exc


@router.get(
    "",
    response_model=KeysListOut,
    dependencies=[require_perm("view", "key:*")],
)
async def list_keys_route(request: Request) -> KeysListOut:
    client = _salt_client_or_503(request)
    try:
        entries = await list_keys(client)
    except (SaltAPIUnavailable, SaltAPIError) as exc:
        raise _wrap_salt_errors(exc) from None
    return KeysListOut(total=len(entries), keys=entries)


@router.post(
    "/{key_id}/accept",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[require_perm("accept", "key:*")],
)
async def accept_key_route(
    key_id: str,
    request: Request,
    db: SessionDep,
    actor: CurrentUser,
) -> Response:
    client = _salt_client_or_503(request)
    try:
        await client.accept_key(key_id)
    except (SaltAPIUnavailable, SaltAPIError) as exc:
        await audit_record(
            db, user_id=actor.id, action="key.accept",
            resource=f"key:{key_id}", args_json=None, salt_jid=None,
            decision="deny", result_code=502,
        )
        await db.commit()
        raise _wrap_salt_errors(exc) from None
    await audit_record(
        db, user_id=actor.id, action="key.accept",
        resource=f"key:{key_id}", args_json=None, salt_jid=None,
        decision="allow", result_code=204,
    )
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/{key_id}/reject",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[require_perm("reject", "key:*")],
)
async def reject_key_route(
    key_id: str,
    request: Request,
    db: SessionDep,
    actor: CurrentUser,
) -> Response:
    client = _salt_client_or_503(request)
    try:
        await client.reject_key(key_id)
    except (SaltAPIUnavailable, SaltAPIError) as exc:
        await audit_record(
            db, user_id=actor.id, action="key.reject",
            resource=f"key:{key_id}", args_json=None, salt_jid=None,
            decision="deny", result_code=502,
        )
        await db.commit()
        raise _wrap_salt_errors(exc) from None
    await audit_record(
        db, user_id=actor.id, action="key.reject",
        resource=f"key:{key_id}", args_json=None, salt_jid=None,
        decision="allow", result_code=204,
    )
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete(
    "/{key_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[require_perm("delete", "key:*")],
)
async def delete_key_route(
    key_id: str,
    request: Request,
    db: SessionDep,
    actor: CurrentUser,
) -> Response:
    client = _salt_client_or_503(request)
    try:
        await client.delete_key(key_id)
    except (SaltAPIUnavailable, SaltAPIError) as exc:
        await audit_record(
            db, user_id=actor.id, action="key.delete",
            resource=f"key:{key_id}", args_json=None, salt_jid=None,
            decision="deny", result_code=502,
        )
        await db.commit()
        raise _wrap_salt_errors(exc) from None
    await audit_record(
        db, user_id=actor.id, action="key.delete",
        resource=f"key:{key_id}", args_json=None, salt_jid=None,
        decision="allow", result_code=204,
    )
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
