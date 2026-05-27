from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from halite.auth.models import User
from halite.auth.password import hash_password
from halite.rbac.models import Role, UserRole

_BOOTSTRAP_USERNAME = "admin"
_BOOTSTRAP_PASSWORD = "changeme"


async def bootstrap_admin(session: AsyncSession) -> None:
    """Create the default admin/changeme user iff no users exist yet.

    Idempotent: a second call is a no-op if any user already exists.
    The bootstrapped user is created with must_change_pw=True so the
    operator is forced to choose a real password on first login.
    """
    user_count = (await session.execute(select(func.count()).select_from(User))).scalar_one()
    if user_count > 0:
        return

    admin_role = (
        await session.execute(select(Role).where(Role.name == "admin"))
    ).scalar_one_or_none()
    if admin_role is None:
        return

    user = User(
        username_lower=_BOOTSTRAP_USERNAME.lower(),
        username=_BOOTSTRAP_USERNAME,
        password_hash=hash_password(_BOOTSTRAP_PASSWORD),
        display_name=_BOOTSTRAP_USERNAME,
        is_active=True,
        is_builtin=True,
        must_change_pw=True,
        created_at=datetime.now(tz=UTC),
    )
    session.add(user)
    await session.flush()
    session.add(UserRole(user_id=user.id, role_id=admin_role.id))
