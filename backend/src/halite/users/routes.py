from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Response, status

from halite.audit.writer import record as audit_record
from halite.auth.service import end_sessions_for_user
from halite.db import SessionDep
from halite.deps import CurrentUser, require_perm
from halite.rbac.schemas import RoleAssignmentPayload
from halite.users.schemas import (
    PasswordResetPayload,
    UserCreatePayload,
    UserListOut,
    UserSummary,
    UserUpdatePayload,
)
from halite.users.service import (
    BuiltinDeletionError,
    DuplicateUsernameError,
    UnknownRoleError,
    add_user_role,
    create_user,
    delete_user,
    get_user,
    list_user_role_ids,
    list_users,
    remove_user_role,
    set_password,
    update_user,
)

router = APIRouter(prefix="/api/users", tags=["users"])


@router.get("", response_model=UserListOut, dependencies=[require_perm("view", "user:*")])
async def list_users_route(
    db: SessionDep,
    limit: Annotated[int, Query(ge=1, le=500)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> UserListOut:
    total, users = await list_users(db, limit=limit, offset=offset)
    return UserListOut(
        total=total,
        users=[UserSummary.model_validate(u, from_attributes=True) for u in users],
    )


@router.get(
    "/{user_id}", response_model=UserSummary, dependencies=[require_perm("view", "user:*")]
)
async def get_user_route(user_id: uuid.UUID, db: SessionDep) -> UserSummary:
    user = await get_user(db, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    return UserSummary.model_validate(user, from_attributes=True)


@router.post(
    "",
    response_model=UserSummary,
    status_code=status.HTTP_201_CREATED,
    dependencies=[require_perm("manage_user", "user:*")],
)
async def create_user_route(
    payload: UserCreatePayload,
    db: SessionDep,
    actor: CurrentUser,
) -> UserSummary:
    try:
        user = await create_user(db, payload)
    except DuplicateUsernameError:
        await audit_record(
            db,
            user_id=actor.id,
            action="user.create",
            resource=f"user:{payload.username}",
            args_json=payload.model_dump(),
            salt_jid=None,
            decision="deny",
            result_code=409,
        )
        await db.commit()
        raise HTTPException(status.HTTP_409_CONFLICT, "Username already exists") from None
    except UnknownRoleError as e:
        await audit_record(
            db,
            user_id=actor.id,
            action="user.create",
            resource=f"user:{payload.username}",
            args_json=payload.model_dump(),
            salt_jid=None,
            decision="deny",
            result_code=400,
        )
        await db.commit()
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, f"Unknown role IDs: {list(e.args[0])}"
        ) from None
    await audit_record(
        db,
        user_id=actor.id,
        action="user.create",
        resource=f"user:{user.username}",
        args_json=payload.model_dump(),
        salt_jid=None,
        decision="allow",
        result_code=201,
    )
    await db.commit()
    return UserSummary.model_validate(user, from_attributes=True)


@router.patch(
    "/{user_id}",
    response_model=UserSummary,
    dependencies=[require_perm("manage_user", "user:*")],
)
async def update_user_route(
    user_id: uuid.UUID,
    payload: UserUpdatePayload,
    db: SessionDep,
    actor: CurrentUser,
) -> UserSummary:
    user = await update_user(db, user_id, payload)
    if user is None:
        await audit_record(
            db,
            user_id=actor.id,
            action="user.update",
            resource=f"user:{user_id}",
            args_json=payload.model_dump(),
            salt_jid=None,
            decision="deny",
            result_code=404,
        )
        await db.commit()
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    await audit_record(
        db,
        user_id=actor.id,
        action="user.update",
        resource=f"user:{user.username}",
        args_json=payload.model_dump(),
        salt_jid=None,
        decision="allow",
        result_code=200,
    )
    await db.commit()
    return UserSummary.model_validate(user, from_attributes=True)


@router.delete(
    "/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[require_perm("manage_user", "user:*")],
)
async def delete_user_route(
    user_id: uuid.UUID,
    db: SessionDep,
    actor: CurrentUser,
):
    if actor.id == user_id:
        await audit_record(
            db,
            user_id=actor.id,
            action="user.delete",
            resource=f"user:{user_id}",
            args_json=None,
            salt_jid=None,
            decision="deny",
            result_code=409,
        )
        await db.commit()
        raise HTTPException(status.HTTP_409_CONFLICT, "Cannot delete yourself")
    try:
        ok = await delete_user(db, user_id)
    except BuiltinDeletionError:
        await audit_record(
            db,
            user_id=actor.id,
            action="user.delete",
            resource=f"user:{user_id}",
            args_json=None,
            salt_jid=None,
            decision="deny",
            result_code=409,
        )
        await db.commit()
        raise HTTPException(status.HTTP_409_CONFLICT, "Cannot delete a built-in user") from None
    if not ok:
        await audit_record(
            db,
            user_id=actor.id,
            action="user.delete",
            resource=f"user:{user_id}",
            args_json=None,
            salt_jid=None,
            decision="deny",
            result_code=404,
        )
        await db.commit()
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    await audit_record(
        db,
        user_id=actor.id,
        action="user.delete",
        resource=f"user:{user_id}",
        args_json=None,
        salt_jid=None,
        decision="allow",
        result_code=204,
    )
    await db.commit()


@router.post(
    "/{user_id}/password",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[require_perm("manage_user", "user:*")],
)
async def reset_password_route(
    user_id: uuid.UUID,
    payload: PasswordResetPayload,
    db: SessionDep,
    actor: CurrentUser,
):
    user = await set_password(db, user_id, payload)
    if user is None:
        await audit_record(
            db, user_id=actor.id, action="user.password_reset",
            resource=f"user:{user_id}",
            args_json=payload.model_dump(), salt_jid=None,
            decision="deny", result_code=404,
        )
        await db.commit()
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    await end_sessions_for_user(db, user_id)
    await audit_record(
        db, user_id=actor.id, action="user.password_reset",
        resource=f"user:{user.username}",
        args_json=payload.model_dump(), salt_jid=None,
        decision="allow", result_code=204,
    )
    await db.commit()


@router.get(
    "/{user_id}/roles",
    response_model=list[uuid.UUID],
    dependencies=[require_perm("view", "user:*")],
)
async def list_user_roles_route(user_id: uuid.UUID, db: SessionDep) -> list[uuid.UUID]:
    user = await get_user(db, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    return await list_user_role_ids(db, user_id)


@router.post(
    "/{user_id}/roles",
    dependencies=[require_perm("manage_user", "user:*")],
)
async def add_user_role_route(
    user_id: uuid.UUID,
    payload: RoleAssignmentPayload,
    db: SessionDep,
    actor: CurrentUser,
):
    result = await add_user_role(db, user_id, payload.role_id)
    payload_json = payload.model_dump(mode="json")
    if result == "unknown_user":
        await audit_record(
            db, user_id=actor.id, action="user.role_add",
            resource=f"user:{user_id}", args_json=payload_json,
            salt_jid=None, decision="deny", result_code=404,
        )
        await db.commit()
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    if result == "unknown_role":
        await audit_record(
            db, user_id=actor.id, action="user.role_add",
            resource=f"user:{user_id}", args_json=payload_json,
            salt_jid=None, decision="deny", result_code=400,
        )
        await db.commit()
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Role not found")
    code = status.HTTP_201_CREATED if result == "created" else status.HTTP_200_OK
    await audit_record(
        db, user_id=actor.id, action="user.role_add",
        resource=f"user:{user_id}", args_json=payload_json,
        salt_jid=None, decision="allow", result_code=code,
    )
    await db.commit()
    return Response(status_code=code)


@router.delete(
    "/{user_id}/roles/{role_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[require_perm("manage_user", "user:*")],
)
async def remove_user_role_route(
    user_id: uuid.UUID,
    role_id: uuid.UUID,
    db: SessionDep,
    actor: CurrentUser,
):
    ok = await remove_user_role(db, user_id, role_id)
    if not ok:
        await audit_record(
            db, user_id=actor.id, action="user.role_remove",
            resource=f"user:{user_id}/role:{role_id}", args_json=None,
            salt_jid=None, decision="deny", result_code=404,
        )
        await db.commit()
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Role assignment not found")
    await audit_record(
        db, user_id=actor.id, action="user.role_remove",
        resource=f"user:{user_id}/role:{role_id}", args_json=None,
        salt_jid=None, decision="allow", result_code=204,
    )
    await db.commit()
