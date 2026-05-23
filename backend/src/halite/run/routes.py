# backend/src/halite/run/routes.py
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, status

from halite.audit.writer import record as audit_record
from halite.db import SessionDep
from halite.deps import CurrentUser, require_perm
from halite.run.schemas import RunCommandIn, RunCommandOut
from halite.run.service import run_command
from halite.salt.client import SaltAPIError, SaltAPIUnavailable
from halite.salt.deps import salt_client_or_503, wrap_salt_errors

router = APIRouter(prefix="/api/run", tags=["run"])


@router.post(
    "",
    response_model=RunCommandOut,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[require_perm("execute", "salt:*")],
)
async def run_command_route(
    payload: RunCommandIn,
    request: Request,
    db: SessionDep,
    actor: CurrentUser,
) -> RunCommandOut:
    client = salt_client_or_503(request)
    try:
        out = await run_command(client, payload)
    except (SaltAPIUnavailable, SaltAPIError) as exc:
        http_exc = wrap_salt_errors(exc)
        await audit_record(
            db, user_id=actor.id, action="salt.run",
            resource=f"salt:{payload.fun}",
            args_json=payload.model_dump(mode="json"),
            salt_jid=None,
            decision="deny", result_code=http_exc.status_code,
        )
        await db.commit()
        raise http_exc from None

    if not out.jid:
        await audit_record(
            db, user_id=actor.id, action="salt.run",
            resource=f"salt:{payload.fun}",
            args_json=payload.model_dump(mode="json"),
            salt_jid=None,
            decision="deny", result_code=502,
        )
        await db.commit()
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "Salt-API returned no jid")

    await audit_record(
        db, user_id=actor.id, action="salt.run",
        resource=f"salt:{payload.fun}",
        args_json=payload.model_dump(mode="json"),
        salt_jid=out.jid,
        decision="allow", result_code=202,
    )
    await db.commit()
    return out
