# backend/src/halite/templates/routes.py
from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, Response, status
from sqlalchemy import select

from halite.audit.writer import record as audit_record
from halite.auth.models import User
from halite.db import SessionDep
from halite.deps import CurrentUser
from halite.templates.schemas import (
    CommandTemplateCreate,
    CommandTemplateListOut,
    CommandTemplateOut,
    TemplateShareUpdate,
)
from halite.templates.service import (
    TemplateNameTaken,
    create,
    delete_own,
    list_visible,
    update_share,
)

router = APIRouter(prefix="/api/templates", tags=["templates"])


@router.get("", response_model=CommandTemplateListOut)
async def list_templates_route(db: SessionDep, actor: CurrentUser) -> CommandTemplateListOut:
    actor_id = actor.id
    rows = await list_visible(db, viewer_user_id=actor_id)
    out = [
        CommandTemplateOut(
            id=tpl.id,
            owner_user_id=tpl.owner_user_id,
            owner_username=username,
            name=tpl.name,
            description=tpl.description,
            target=tpl.target,
            target_type=tpl.target_type,
            fun=tpl.fun,
            args=tpl.args,
            kwargs=tpl.kwargs,
            is_shared=tpl.is_shared,
            created_at=tpl.created_at,
            updated_at=tpl.updated_at,
        )
        for tpl, username in rows
    ]
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
    user_row = await db.execute(
        select(User.username).where(User.id == actor_id)
    )
    owner_username = user_row.scalar_one()
    return CommandTemplateOut(
        id=tpl.id,
        owner_user_id=tpl.owner_user_id,
        owner_username=owner_username,
        name=tpl.name,
        description=tpl.description,
        target=tpl.target,
        target_type=tpl.target_type,
        fun=tpl.fun,
        args=tpl.args,
        kwargs=tpl.kwargs,
        is_shared=tpl.is_shared,
        created_at=tpl.created_at,
        updated_at=tpl.updated_at,
    )


@router.delete(
    "/{template_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_template_route(
    template_id: uuid.UUID,
    db: SessionDep,
    actor: CurrentUser,
) -> Response:
    actor_id = actor.id
    deleted = await delete_own(db, owner_user_id=actor_id, template_id=template_id)
    if not deleted:
        # No info-leak: always 404 if not owned by actor.
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Template not found")
    await audit_record(
        db, user_id=actor_id, action="template.delete",
        resource=f"template:{template_id}",
        args_json=None, salt_jid=None,
        decision="allow", result_code=204,
    )
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.patch(
    "/{template_id}",
    response_model=CommandTemplateOut,
)
async def update_template_route(
    template_id: uuid.UUID,
    body: TemplateShareUpdate,
    db: SessionDep,
    actor: CurrentUser,
) -> CommandTemplateOut:
    actor_id = actor.id
    tpl = await update_share(
        db,
        owner_user_id=actor_id,
        template_id=template_id,
        is_shared=body.is_shared,
    )
    if tpl is None:
        # 404 not 403 — same info-leak guard as DELETE
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Template not found")

    action = "template.share" if body.is_shared else "template.unshare"
    await audit_record(
        db, user_id=actor_id, action=action,
        resource=f"template:{template_id}",
        args_json={"is_shared": body.is_shared},
        salt_jid=None,
        decision="allow", result_code=200,
    )
    await db.commit()
    await db.refresh(tpl)

    user_row = await db.execute(
        select(User.username).where(User.id == actor_id)
    )
    owner_username = user_row.scalar_one()
    return CommandTemplateOut(
        id=tpl.id,
        owner_user_id=tpl.owner_user_id,
        owner_username=owner_username,
        name=tpl.name,
        description=tpl.description,
        target=tpl.target,
        target_type=tpl.target_type,
        fun=tpl.fun,
        args=tpl.args,
        kwargs=tpl.kwargs,
        is_shared=tpl.is_shared,
        created_at=tpl.created_at,
        updated_at=tpl.updated_at,
    )
