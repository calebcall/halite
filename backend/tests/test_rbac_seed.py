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


@pytest.mark.asyncio
async def test_seed_fills_permission_gaps_on_existing_role(session):
    """Simulates a deployment that upgraded from an earlier plan: the
    ``operator`` role already exists but only has a subset of the seeded
    permissions. ``seed_builtin_roles`` must fill the gap (notably the
    new ``execute:salt:*`` grant introduced in Plan 12) without
    duplicating the existing row, and must remain idempotent on a
    second call.
    """
    # Pre-create the operator role with a single legacy permission.
    legacy_role = Role(
        name="operator",
        is_builtin=True,
        description="Run salt commands and manage keys, but no user administration.",
    )
    session.add(legacy_role)
    await session.flush()
    session.add(
        Permission(role_id=legacy_role.id, verb="accept", resource_glob="key:*")
    )
    await session.commit()

    await seed_builtin_roles(session)
    await session.commit()

    role = (
        await session.execute(select(Role).where(Role.name == "operator"))
    ).scalar_one()
    perms = (
        await session.execute(select(Permission).where(Permission.role_id == role.id))
    ).scalars().all()
    pairs = {(p.verb, p.resource_glob) for p in perms}

    expected = {
        ("view", "*"),
        ("run", "*"),
        ("accept", "key:*"),
        ("delete", "key:*"),
        ("execute", "salt:*"),
        ("reject", "key:*"),
    }
    assert expected.issubset(pairs), f"missing permissions: {expected - pairs}"
    # The legacy permission must not have been duplicated.
    assert len(perms) == len(pairs)

    # Second invocation must not introduce duplicate rows.
    await seed_builtin_roles(session)
    await session.commit()
    perms_again = (
        await session.execute(select(Permission).where(Permission.role_id == role.id))
    ).scalars().all()
    assert len(perms_again) == len(perms)
