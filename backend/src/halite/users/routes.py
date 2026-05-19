from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status

from halite.db import SessionDep
from halite.deps import require_perm
from halite.users.schemas import UserListOut, UserSummary
from halite.users.service import get_user, list_users

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
