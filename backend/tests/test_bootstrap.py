from datetime import UTC, datetime

import pytest
from sqlalchemy import select

from halite.auth.models import User
from halite.auth.password import verify_password
from halite.bootstrap import bootstrap_admin
from halite.rbac.models import Role, UserRole
from halite.rbac.seed import seed_builtin_roles


@pytest.mark.asyncio
async def test_bootstrap_creates_admin_when_no_users_exist(session, app_db):
    await seed_builtin_roles(session)
    await session.commit()

    await bootstrap_admin(session)
    await session.commit()

    user = (await session.execute(select(User).where(User.username == "admin"))).scalar_one()
    assert verify_password(user.password_hash, "changeme")
    assert user.is_active is True
    assert user.is_builtin is True
    assert user.must_change_pw is True

    admin_role = (await session.execute(select(Role).where(Role.name == "admin"))).scalar_one()
    link = (
        await session.execute(
            select(UserRole).where(UserRole.user_id == user.id, UserRole.role_id == admin_role.id)
        )
    ).scalar_one()
    assert link is not None


@pytest.mark.asyncio
async def test_bootstrap_skips_when_users_already_exist(session, app_db):
    await seed_builtin_roles(session)
    session.add(
        User(
            username_lower="someone", username="Someone",
            password_hash="$argon2id$v=19$m=65536,t=3,p=4$abc$def",
            is_active=True, created_at=datetime.now(tz=UTC),
        )
    )
    await session.commit()
    await bootstrap_admin(session)
    await session.commit()
    rows = (await session.execute(select(User))).scalars().all()
    assert len(rows) == 1
    assert rows[0].username == "Someone"
