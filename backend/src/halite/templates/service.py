# backend/src/halite/templates/service.py
from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from halite.templates.models import CommandTemplate
from halite.templates.schemas import CommandTemplateCreate


class TemplateNameTaken(Exception):
    """Owner already has a template with this name."""


async def list_own(
    db: AsyncSession, *, owner_user_id: uuid.UUID
) -> list[CommandTemplate]:
    rows = await db.execute(
        select(CommandTemplate)
        .where(CommandTemplate.owner_user_id == owner_user_id)
        .order_by(CommandTemplate.created_at.desc())
    )
    return list(rows.scalars().all())


async def create(
    db: AsyncSession,
    *,
    owner_user_id: uuid.UUID,
    payload: CommandTemplateCreate,
) -> CommandTemplate:
    now = datetime.now(tz=UTC)
    tpl = CommandTemplate(
        owner_user_id=owner_user_id,
        name=payload.name,
        description=payload.description,
        target=payload.target,
        target_type=payload.target_type,
        fun=payload.fun,
        args=list(payload.args),
        kwargs=dict(payload.kwargs),
        created_at=now,
        updated_at=now,
    )
    db.add(tpl)
    try:
        await db.flush()
    except IntegrityError as exc:
        await db.rollback()
        raise TemplateNameTaken from exc
    return tpl


async def delete_own(
    db: AsyncSession,
    *,
    owner_user_id: uuid.UUID,
    template_id: uuid.UUID,
) -> bool:
    """Delete only if owned by owner_user_id. Returns True if a row was
    deleted; False otherwise (route decides 204 vs 404)."""
    rows = await db.execute(
        select(CommandTemplate).where(
            CommandTemplate.id == template_id,
            CommandTemplate.owner_user_id == owner_user_id,
        )
    )
    tpl = rows.scalar_one_or_none()
    if tpl is None:
        return False
    await db.delete(tpl)
    return True
