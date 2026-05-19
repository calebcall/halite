# backend/src/halite/users/service.py
from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import delete as sa_delete
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from halite.auth.models import User
from halite.auth.password import hash_password
from halite.db_dialect import lower_eq
from halite.rbac.models import Role, UserRole
from halite.users.schemas import PasswordResetPayload, UserCreatePayload, UserUpdatePayload


class DuplicateUsernameError(Exception):
    """Raised when a username (case-insensitive) is already taken."""


class UnknownRoleError(Exception):
    """Raised when role_ids reference roles that don't exist."""


class BuiltinDeletionError(Exception):
    """Raised when attempting to delete a built-in user."""


async def create_user(session: AsyncSession, payload: UserCreatePayload) -> User:
    existing = (
        await session.execute(select(User).where(lower_eq(User.username_lower, payload.username)))
    ).scalar_one_or_none()
    if existing is not None:
        raise DuplicateUsernameError(payload.username)

    if payload.role_ids:
        found = (
            await session.execute(select(Role.id).where(Role.id.in_(payload.role_ids)))
        ).scalars().all()
        missing = set(payload.role_ids) - set(found)
        if missing:
            raise UnknownRoleError(sorted(str(m) for m in missing))

    user = User(
        username_lower=payload.username.lower(),
        username=payload.username,
        password_hash=hash_password(payload.password),
        display_name=payload.display_name,
        email_lower=payload.email.lower() if payload.email else None,
        email=str(payload.email) if payload.email else None,
        is_active=True,
        is_builtin=False,
        must_change_pw=payload.must_change_pw,
        created_at=datetime.now(tz=UTC),
    )
    session.add(user)
    await session.flush()
    for role_id in payload.role_ids:
        session.add(UserRole(user_id=user.id, role_id=role_id))
    return user


async def get_user(session: AsyncSession, user_id: uuid.UUID) -> User | None:
    return (await session.execute(select(User).where(User.id == user_id))).scalar_one_or_none()


async def list_users(
    session: AsyncSession, *, limit: int = 50, offset: int = 0
) -> tuple[int, list[User]]:
    total = (await session.execute(select(func.count()).select_from(User))).scalar_one()
    rows = (
        await session.execute(
            select(User).order_by(User.username_lower.asc()).limit(limit).offset(offset)
        )
    ).scalars().all()
    return total, list(rows)


async def update_user(
    session: AsyncSession, user_id: uuid.UUID, payload: UserUpdatePayload
) -> User | None:
    user = await get_user(session, user_id)
    if user is None:
        return None
    if payload.display_name is not None:
        user.display_name = payload.display_name
    if payload.email is not None:
        user.email = str(payload.email)
        user.email_lower = str(payload.email).lower()
    if payload.is_active is not None:
        user.is_active = payload.is_active
    return user


async def delete_user(session: AsyncSession, user_id: uuid.UUID) -> bool:
    user = await get_user(session, user_id)
    if user is None:
        return False
    if user.is_builtin:
        raise BuiltinDeletionError(str(user_id))
    await session.execute(sa_delete(User).where(User.id == user_id))
    return True


async def set_password(
    session: AsyncSession, user_id: uuid.UUID, payload: PasswordResetPayload
) -> User | None:
    user = await get_user(session, user_id)
    if user is None:
        return None
    user.password_hash = hash_password(payload.new_password)
    user.must_change_pw = payload.must_change_pw
    return user
