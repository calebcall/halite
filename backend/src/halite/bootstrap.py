from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from halite.auth.models import User
from halite.auth.password import hash_password
from halite.config import Settings
from halite.rbac.models import Role, UserRole


async def bootstrap_admin(session: AsyncSession, settings: Settings) -> None:
    """Create the bootstrap admin from env vars iff no users exist yet.

    Idempotent: a second call is a no-op if any user already exists, or if the
    bootstrap env vars are unset.
    """
    if not settings.bootstrap_admin_username or not settings.bootstrap_admin_password:
        return

    user_count = (await session.execute(select(func.count()).select_from(User))).scalar_one()
    if user_count > 0:
        return

    admin_role = (
        await session.execute(select(Role).where(Role.name == "admin"))
    ).scalar_one_or_none()
    if admin_role is None:
        return

    user = User(
        username_lower=settings.bootstrap_admin_username.lower(),
        username=settings.bootstrap_admin_username,
        password_hash=hash_password(settings.bootstrap_admin_password),
        display_name=settings.bootstrap_admin_username,
        is_active=True,
        is_builtin=True,
        must_change_pw=True,
        created_at=datetime.now(tz=UTC),
    )
    session.add(user)
    await session.flush()
    session.add(UserRole(user_id=user.id, role_id=admin_role.id))
