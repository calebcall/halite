import pytest
from sqlalchemy import select

from halite.rbac.models import Permission, Role
from halite.rbac.seed import seed_builtin_roles


@pytest.mark.asyncio
async def test_seed_creates_three_builtin_roles(session):
    await seed_builtin_roles(session)
    await session.commit()
    result = await session.execute(select(Role).order_by(Role.name))
    names = [r.name for r in result.scalars().all()]
    assert names == ["admin", "operator", "viewer"]


@pytest.mark.asyncio
async def test_seed_admin_has_full_access(session):
    await seed_builtin_roles(session)
    await session.commit()
    role = (await session.execute(select(Role).where(Role.name == "admin"))).scalar_one()
    perms = (
        await session.execute(select(Permission).where(Permission.role_id == role.id))
    ).scalars().all()
    pairs = {(p.verb, p.resource_glob) for p in perms}
    assert ("*", "*") in pairs


@pytest.mark.asyncio
async def test_seed_is_idempotent(session):
    await seed_builtin_roles(session)
    await session.commit()
    await seed_builtin_roles(session)
    await session.commit()
    count = (await session.execute(select(Role))).scalars().all()
    assert len(count) == 3
