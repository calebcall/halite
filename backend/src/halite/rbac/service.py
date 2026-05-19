from __future__ import annotations

import uuid

from sqlalchemy import delete as sa_delete
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from halite.rbac.models import Permission, Role
from halite.rbac.schemas import PermissionPayload, RoleCreatePayload, RoleUpdatePayload


class DuplicateRoleNameError(Exception):
    pass


class BuiltinRoleError(Exception):
    pass


async def create_role(session: AsyncSession, payload: RoleCreatePayload) -> Role:
    existing = (
        await session.execute(select(Role).where(Role.name == payload.name))
    ).scalar_one_or_none()
    if existing is not None:
        raise DuplicateRoleNameError(payload.name)
    role = Role(name=payload.name, is_builtin=False, description=payload.description)
    session.add(role)
    await session.flush()
    return role


async def get_role(session: AsyncSession, role_id: uuid.UUID) -> Role | None:
    return (await session.execute(select(Role).where(Role.id == role_id))).scalar_one_or_none()


async def list_roles(
    session: AsyncSession, *, limit: int = 50, offset: int = 0
) -> tuple[int, list[Role]]:
    total = (await session.execute(select(func.count()).select_from(Role))).scalar_one()
    rows = (
        await session.execute(
            select(Role).order_by(Role.name.asc()).limit(limit).offset(offset)
        )
    ).scalars().all()
    return total, list(rows)


async def update_role(
    session: AsyncSession, role_id: uuid.UUID, payload: RoleUpdatePayload
) -> Role | None:
    role = await get_role(session, role_id)
    if role is None:
        return None
    if payload.description is not None:
        role.description = payload.description
    return role


async def delete_role(session: AsyncSession, role_id: uuid.UUID) -> bool:
    role = await get_role(session, role_id)
    if role is None:
        return False
    if role.is_builtin:
        raise BuiltinRoleError(str(role_id))
    await session.execute(sa_delete(Role).where(Role.id == role_id))
    return True


async def list_permissions(session: AsyncSession, role_id: uuid.UUID) -> list[Permission]:
    rows = (
        await session.execute(select(Permission).where(Permission.role_id == role_id))
    ).scalars().all()
    return list(rows)


async def add_permission(
    session: AsyncSession, role_id: uuid.UUID, payload: PermissionPayload
) -> Permission:
    perm = Permission(role_id=role_id, verb=payload.verb, resource_glob=payload.resource_glob)
    session.add(perm)
    await session.flush()
    return perm


async def remove_permission(
    session: AsyncSession, role_id: uuid.UUID, permission_id: uuid.UUID
) -> bool:
    perm = (
        await session.execute(
            select(Permission)
            .where(Permission.id == permission_id)
            .where(Permission.role_id == role_id)
        )
    ).scalar_one_or_none()
    if perm is None:
        return False
    await session.execute(sa_delete(Permission).where(Permission.id == permission_id))
    return True
