import pytest
from sqlalchemy import select

from halite.rbac.models import Permission, Role
from halite.rbac.schemas import (
    PermissionPayload,
    RoleCreatePayload,
    RoleUpdatePayload,
)
from halite.rbac.service import (
    BuiltinRoleError,
    DuplicateRoleNameError,
    add_permission,
    create_role,
    delete_role,
    get_role,
    list_roles,
    remove_permission,
    update_role,
)


@pytest.mark.asyncio
async def test_create_role_persists(session):
    role = await create_role(session, RoleCreatePayload(name="ops", description="Ops team"))
    await session.commit()
    fetched = (await session.execute(select(Role).where(Role.id == role.id))).scalar_one()
    assert fetched.name == "ops"
    assert fetched.is_builtin is False


@pytest.mark.asyncio
async def test_create_role_rejects_duplicate_name(session):
    await create_role(session, RoleCreatePayload(name="ops"))
    await session.commit()
    with pytest.raises(DuplicateRoleNameError):
        await create_role(session, RoleCreatePayload(name="ops"))


@pytest.mark.asyncio
async def test_update_role_changes_description(session):
    role = await create_role(session, RoleCreatePayload(name="ops"))
    await session.commit()
    updated = await update_role(session, role.id, RoleUpdatePayload(description="New"))
    await session.commit()
    assert updated.description == "New"


@pytest.mark.asyncio
async def test_delete_role_removes_row(session):
    role = await create_role(session, RoleCreatePayload(name="ops"))
    await session.commit()
    ok = await delete_role(session, role.id)
    await session.commit()
    assert ok is True
    assert await get_role(session, role.id) is None


@pytest.mark.asyncio
async def test_delete_role_refuses_builtin(session):
    role = await create_role(session, RoleCreatePayload(name="ops"))
    role.is_builtin = True
    await session.commit()
    with pytest.raises(BuiltinRoleError):
        await delete_role(session, role.id)


@pytest.mark.asyncio
async def test_list_roles_with_pagination(session):
    for i in range(4):
        await create_role(session, RoleCreatePayload(name=f"r{i}"))
    await session.commit()
    total, roles = await list_roles(session, limit=2, offset=0)
    assert total == 4
    assert len(roles) == 2


@pytest.mark.asyncio
async def test_add_permission_creates_row(session):
    role = await create_role(session, RoleCreatePayload(name="ops"))
    await session.commit()
    perm = await add_permission(
        session, role.id, PermissionPayload(verb="run", resource_glob="state.*")
    )
    await session.commit()
    assert perm.role_id == role.id
    assert perm.verb == "run"


@pytest.mark.asyncio
async def test_remove_permission_deletes_row(session):
    role = await create_role(session, RoleCreatePayload(name="ops"))
    await session.commit()
    perm = await add_permission(
        session, role.id, PermissionPayload(verb="run", resource_glob="state.*")
    )
    await session.commit()
    ok = await remove_permission(session, role.id, perm.id)
    await session.commit()
    assert ok is True
    remaining = (
        await session.execute(select(Permission).where(Permission.id == perm.id))
    ).scalar_one_or_none()
    assert remaining is None


@pytest.mark.asyncio
async def test_remove_permission_404_when_mismatched_role(session):
    role_a = await create_role(session, RoleCreatePayload(name="a"))
    role_b = await create_role(session, RoleCreatePayload(name="b"))
    await session.commit()
    perm = await add_permission(
        session, role_a.id, PermissionPayload(verb="run", resource_glob="state.*")
    )
    await session.commit()
    ok = await remove_permission(session, role_b.id, perm.id)
    assert ok is False
