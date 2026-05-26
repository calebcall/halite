# backend/src/halite/templates/service.py
from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import case, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from halite.auth.models import User
from halite.templates.models import CommandTemplate
from halite.templates.schemas import CommandTemplateCreate


class TemplateNameTaken(Exception):
    """Owner already has a template with this name."""


async def list_visible(
    db: AsyncSession, *, viewer_user_id: uuid.UUID
) -> list[tuple[CommandTemplate, str]]:
    """Return (template, owner_username) tuples for templates visible to
    the viewer: their own + shared-from-others. Own templates sort first
    (newest first), then shared-from-others (newest first)."""
    is_own = (CommandTemplate.owner_user_id == viewer_user_id)
    stmt = (
        select(CommandTemplate, User.username)
        .join(User, CommandTemplate.owner_user_id == User.id)
        .where(or_(is_own, CommandTemplate.is_shared.is_(True)))
        .order_by(
            case((is_own, 0), else_=1),
            CommandTemplate.created_at.desc(),
        )
    )
    rows = await db.execute(stmt)
    return [(tpl, username) for tpl, username in rows.all()]


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
        is_shared=payload.is_shared,
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


async def update_share(
    db: AsyncSession,
    *,
    owner_user_id: uuid.UUID,
    template_id: uuid.UUID,
    is_shared: bool,
) -> CommandTemplate | None:
    """Toggle is_shared. Returns the updated template, or None if the
    template isn't owned by owner_user_id."""
    rows = await db.execute(
        select(CommandTemplate).where(
            CommandTemplate.id == template_id,
            CommandTemplate.owner_user_id == owner_user_id,
        )
    )
    tpl = rows.scalar_one_or_none()
    if tpl is None:
        return None
    if tpl.is_shared != is_shared:
        tpl.is_shared = is_shared
        tpl.updated_at = datetime.now(tz=UTC)
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
