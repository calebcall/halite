# backend/src/halite/templates/routes.py
from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, Response, status

from halite.audit.writer import record as audit_record
from halite.db import SessionDep
from halite.deps import CurrentUser
from halite.templates.schemas import (
    CommandTemplateCreate,
    CommandTemplateListOut,
    CommandTemplateOut,
)
from halite.templates.service import (
    TemplateNameTaken,
    create,
    delete_own,
    list_own,
)

router = APIRouter(prefix="/api/templates", tags=["templates"])


@router.get("", response_model=CommandTemplateListOut)
async def list_templates_route(db: SessionDep, actor: CurrentUser) -> CommandTemplateListOut:
    rows = await list_own(db, owner_user_id=actor.id)
    out = [CommandTemplateOut.model_validate(r) for r in rows]
    return CommandTemplateListOut(total=len(out), templates=out)


@router.post(
    "",
    response_model=CommandTemplateOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_template_route(
    payload: CommandTemplateCreate,
    db: SessionDep,
    actor: CurrentUser,
) -> CommandTemplateOut:
    # Capture actor id before any potential rollback so we can still write
    # the audit row even after service.create() rolls back on conflict.
    actor_id = actor.id
    try:
        tpl = await create(db, owner_user_id=actor_id, payload=payload)
    except TemplateNameTaken:
        await audit_record(
            db, user_id=actor_id, action="template.create",
            resource=f"template:{payload.name}",
            args_json=payload.model_dump(mode="json"),
            salt_jid=None,
            decision="deny", result_code=409,
        )
        await db.commit()
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Template name already exists"
        ) from None

    await audit_record(
        db, user_id=actor_id, action="template.create",
        resource=f"template:{tpl.id}",
        args_json=payload.model_dump(mode="json"),
        salt_jid=None,
        decision="allow", result_code=201,
    )
    await db.commit()
    await db.refresh(tpl)
    return CommandTemplateOut.model_validate(tpl)


@router.delete(
    "/{template_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_template_route(
    template_id: uuid.UUID,
    db: SessionDep,
    actor: CurrentUser,
) -> Response:
    deleted = await delete_own(db, owner_user_id=actor.id, template_id=template_id)
    if not deleted:
        # No info-leak: always 404 if not owned by actor.
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Template not found")
    await audit_record(
        db, user_id=actor.id, action="template.delete",
        resource=f"template:{template_id}",
        args_json=None, salt_jid=None,
        decision="allow", result_code=204,
    )
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
