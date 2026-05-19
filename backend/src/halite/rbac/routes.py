from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, status

from halite.audit.writer import record as audit_record
from halite.db import SessionDep
from halite.deps import CurrentUser, require_perm
from halite.rbac.schemas import (
    PermissionOut,
    RoleCreatePayload,
    RoleDetail,
    RoleListOut,
    RoleSummary,
    RoleUpdatePayload,
)
from halite.rbac.service import (
    BuiltinRoleError,
    DuplicateRoleNameError,
    create_role,
    delete_role,
    get_role,
    list_permissions,
    list_roles,
    update_role,
)

router = APIRouter(prefix="/api/roles", tags=["roles"])


@router.get("", response_model=RoleListOut, dependencies=[require_perm("view", "role:*")])
async def list_roles_route(db: SessionDep) -> RoleListOut:
    total, roles = await list_roles(db)
    return RoleListOut(
        total=total, roles=[RoleSummary.model_validate(r, from_attributes=True) for r in roles]
    )


@router.get(
    "/{role_id}", response_model=RoleDetail, dependencies=[require_perm("view", "role:*")]
)
async def get_role_route(role_id: uuid.UUID, db: SessionDep) -> RoleDetail:
    role = await get_role(db, role_id)
    if role is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Role not found")
    perms = await list_permissions(db, role_id)
    return RoleDetail(
        id=role.id,
        name=role.name,
        is_builtin=role.is_builtin,
        description=role.description,
        permissions=[PermissionOut.model_validate(p, from_attributes=True) for p in perms],
    )


@router.post(
    "",
    response_model=RoleSummary,
    status_code=status.HTTP_201_CREATED,
    dependencies=[require_perm("manage_role", "role:*")],
)
async def create_role_route(
    payload: RoleCreatePayload, db: SessionDep, actor: CurrentUser
) -> RoleSummary:
    try:
        role = await create_role(db, payload)
    except DuplicateRoleNameError:
        await audit_record(
            db,
            user_id=actor.id,
            action="role.create",
            resource=f"role:{payload.name}",
            args_json=payload.model_dump(),
            salt_jid=None,
            decision="deny",
            result_code=409,
        )
        await db.commit()
        raise HTTPException(status.HTTP_409_CONFLICT, "Role name already exists") from None
    await audit_record(
        db,
        user_id=actor.id,
        action="role.create",
        resource=f"role:{role.name}",
        args_json=payload.model_dump(),
        salt_jid=None,
        decision="allow",
        result_code=201,
    )
    await db.commit()
    return RoleSummary.model_validate(role, from_attributes=True)


@router.patch(
    "/{role_id}",
    response_model=RoleSummary,
    dependencies=[require_perm("manage_role", "role:*")],
)
async def update_role_route(
    role_id: uuid.UUID,
    payload: RoleUpdatePayload,
    db: SessionDep,
    actor: CurrentUser,
) -> RoleSummary:
    role = await update_role(db, role_id, payload)
    if role is None:
        await audit_record(
            db,
            user_id=actor.id,
            action="role.update",
            resource=f"role:{role_id}",
            args_json=payload.model_dump(),
            salt_jid=None,
            decision="deny",
            result_code=404,
        )
        await db.commit()
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Role not found")
    await audit_record(
        db,
        user_id=actor.id,
        action="role.update",
        resource=f"role:{role.name}",
        args_json=payload.model_dump(),
        salt_jid=None,
        decision="allow",
        result_code=200,
    )
    await db.commit()
    return RoleSummary.model_validate(role, from_attributes=True)


@router.delete(
    "/{role_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[require_perm("manage_role", "role:*")],
)
async def delete_role_route(role_id: uuid.UUID, db: SessionDep, actor: CurrentUser):
    try:
        ok = await delete_role(db, role_id)
    except BuiltinRoleError:
        await audit_record(
            db,
            user_id=actor.id,
            action="role.delete",
            resource=f"role:{role_id}",
            args_json=None,
            salt_jid=None,
            decision="deny",
            result_code=409,
        )
        await db.commit()
        raise HTTPException(status.HTTP_409_CONFLICT, "Cannot delete a built-in role") from None
    if not ok:
        await audit_record(
            db,
            user_id=actor.id,
            action="role.delete",
            resource=f"role:{role_id}",
            args_json=None,
            salt_jid=None,
            decision="deny",
            result_code=404,
        )
        await db.commit()
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Role not found")
    await audit_record(
        db,
        user_id=actor.id,
        action="role.delete",
        resource=f"role:{role_id}",
        args_json=None,
        salt_jid=None,
        decision="allow",
        result_code=204,
    )
    await db.commit()
