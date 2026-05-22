# backend/src/halite/keys/routes.py
from __future__ import annotations

from fastapi import APIRouter, Request, Response, status

from halite.audit.writer import record as audit_record
from halite.db import SessionDep
from halite.deps import CurrentUser, require_perm
from halite.keys.schemas import KeysListOut
from halite.keys.service import list_keys
from halite.salt.client import SaltAPIError, SaltAPIUnavailable
from halite.salt.deps import salt_client_or_503, wrap_salt_errors

router = APIRouter(prefix="/api/keys", tags=["keys"])


@router.get(
    "",
    response_model=KeysListOut,
    dependencies=[require_perm("view", "key:*")],
)
async def list_keys_route(request: Request) -> KeysListOut:
    client = salt_client_or_503(request)
    try:
        entries = await list_keys(client)
    except (SaltAPIUnavailable, SaltAPIError) as exc:
        raise wrap_salt_errors(exc) from None
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
    client = salt_client_or_503(request)
    try:
        await client.accept_key(key_id)
    except (SaltAPIUnavailable, SaltAPIError) as exc:
        http_exc = wrap_salt_errors(exc)
        await audit_record(
            db, user_id=actor.id, action="key.accept",
            resource=f"key:{key_id}", args_json=None, salt_jid=None,
            decision="deny", result_code=http_exc.status_code,
        )
        await db.commit()
        raise http_exc from None
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
    client = salt_client_or_503(request)
    try:
        await client.reject_key(key_id)
    except (SaltAPIUnavailable, SaltAPIError) as exc:
        http_exc = wrap_salt_errors(exc)
        await audit_record(
            db, user_id=actor.id, action="key.reject",
            resource=f"key:{key_id}", args_json=None, salt_jid=None,
            decision="deny", result_code=http_exc.status_code,
        )
        await db.commit()
        raise http_exc from None
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
    client = salt_client_or_503(request)
    try:
        await client.delete_key(key_id)
    except (SaltAPIUnavailable, SaltAPIError) as exc:
        http_exc = wrap_salt_errors(exc)
        await audit_record(
            db, user_id=actor.id, action="key.delete",
            resource=f"key:{key_id}", args_json=None, salt_jid=None,
            decision="deny", result_code=http_exc.status_code,
        )
        await db.commit()
        raise http_exc from None
    await audit_record(
        db, user_id=actor.id, action="key.delete",
        resource=f"key:{key_id}", args_json=None, salt_jid=None,
        decision="allow", result_code=204,
    )
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
