# backend/tests/test_users_service.py

import pytest
from sqlalchemy import select

from halite.auth.models import User
from halite.auth.password import verify_password
from halite.rbac.models import Role, UserRole
from halite.users.schemas import UserCreatePayload, UserUpdatePayload
from halite.users.service import (
    DuplicateUsernameError,
    UnknownRoleError,
    create_user,
    delete_user,
    get_user,
    list_users,
    update_user,
)


async def _seed_role(session, name: str) -> Role:
    role = Role(name=name, is_builtin=False, description="")
    session.add(role)
    await session.flush()
    await session.commit()
    return role


@pytest.mark.asyncio
async def test_create_user_persists_with_hashed_password(session):
    payload = UserCreatePayload(
        username="alice",
        display_name="Alice",
        password="hunter2-strong",
        must_change_pw=False,
    )
    user = await create_user(session, payload)
    await session.commit()

    fetched = (await session.execute(select(User).where(User.id == user.id))).scalar_one()
    assert fetched.username == "alice"
    assert fetched.username_lower == "alice"
    assert verify_password(fetched.password_hash, "hunter2-strong")
    assert fetched.must_change_pw is False


@pytest.mark.asyncio
async def test_create_user_rejects_duplicate_username_case_insensitively(session):
    await create_user(session, UserCreatePayload(username="Alice", password="hunter2-strong"))
    await session.commit()
    with pytest.raises(DuplicateUsernameError):
        await create_user(session, UserCreatePayload(username="ALICE", password="hunter2-strong"))


@pytest.mark.asyncio
async def test_create_user_assigns_initial_roles(session):
    role = await _seed_role(session, "operator-ish")
    user = await create_user(
        session,
        UserCreatePayload(username="bob", password="hunter2-strong", role_ids=[role.id]),
    )
    await session.commit()
    links = (
        await session.execute(select(UserRole).where(UserRole.user_id == user.id))
    ).scalars().all()
    assert [l.role_id for l in links] == [role.id]


@pytest.mark.asyncio
async def test_create_user_rejects_unknown_role(session):
    import uuid
    with pytest.raises(UnknownRoleError):
        await create_user(
            session,
            UserCreatePayload(
                username="bob", password="hunter2-strong", role_ids=[uuid.uuid4()]
            ),
        )


@pytest.mark.asyncio
async def test_list_users_returns_all_with_pagination(session):
    for i in range(5):
        await create_user(session, UserCreatePayload(username=f"u{i}", password="hunter2-strong"))
    await session.commit()
    total, users = await list_users(session, limit=2, offset=0)
    assert total == 5
    assert len(users) == 2


@pytest.mark.asyncio
async def test_get_user_returns_none_for_unknown(session):
    import uuid
    assert await get_user(session, uuid.uuid4()) is None


@pytest.mark.asyncio
async def test_update_user_changes_fields(session):
    user = await create_user(session, UserCreatePayload(username="alice", password="hunter2-strong"))
    await session.commit()
    updated = await update_user(
        session, user.id, UserUpdatePayload(display_name="Alice Smith", is_active=False)
    )
    await session.commit()
    assert updated.display_name == "Alice Smith"
    assert updated.is_active is False


@pytest.mark.asyncio
async def test_delete_user_removes_row(session):
    user = await create_user(session, UserCreatePayload(username="alice", password="hunter2-strong"))
    await session.commit()
    ok = await delete_user(session, user.id)
    await session.commit()
    assert ok is True
    assert await get_user(session, user.id) is None


@pytest.mark.asyncio
async def test_delete_user_refuses_builtin(session):
    user = await create_user(session, UserCreatePayload(username="root", password="hunter2-strong"))
    user.is_builtin = True
    await session.commit()
    from halite.users.service import BuiltinDeletionError
    with pytest.raises(BuiltinDeletionError):
        await delete_user(session, user.id)
