from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status

from halite.audit.writer import record as audit_record
from halite.db import SessionDep
from halite.deps import CurrentUser, require_perm
from halite.users.schemas import UserCreatePayload, UserListOut, UserSummary
from halite.users.service import (
    DuplicateUsernameError,
    UnknownRoleError,
    create_user,
    get_user,
    list_users,
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
        raise HTTPException(status.HTTP_409_CONFLICT, "Username already exists")
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
        )
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
