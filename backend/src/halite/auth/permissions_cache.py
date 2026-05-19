from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from halite.auth.models import User
from halite.rbac.models import Permission, UserRole


async def load_permissions_for(session: AsyncSession, user: User) -> list[tuple[str, str]]:
    stmt = (
        select(Permission.verb, Permission.resource_glob)
        .join(UserRole, UserRole.role_id == Permission.role_id)
        .where(UserRole.user_id == user.id)
    )
    return [(v, g) for v, g in (await session.execute(stmt)).all()]
