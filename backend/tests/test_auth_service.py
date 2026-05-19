from datetime import UTC, datetime

import pytest
from sqlalchemy import select

from halite.auth.models import Session, User
from halite.auth.password import hash_password
from halite.auth.service import (
    LoginResult,
    create_session,
    end_session,
    login,
    lookup_session,
)


async def _make_user(session, username: str, password: str) -> User:
    user = User(
        username_lower=username.lower(),
        username=username,
        password_hash=hash_password(password),
        display_name=username,
        is_active=True,
        created_at=datetime.now(tz=UTC),
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


@pytest.mark.asyncio
async def test_login_succeeds_with_correct_password(session):
    await _make_user(session, "alice", "hunter2")
    result = await login(session, "alice", "hunter2", user_agent="ua", ip="1.2.3.4")
    assert isinstance(result, LoginResult)
    assert result.session_id is not None
    assert result.user.username == "alice"


@pytest.mark.asyncio
async def test_login_is_case_insensitive_on_username(session):
    await _make_user(session, "Alice", "hunter2")
    result = await login(session, "ALICE", "hunter2", user_agent="ua", ip="1.2.3.4")
    assert result is not None and result.user.username == "Alice"


@pytest.mark.asyncio
async def test_login_fails_with_wrong_password(session):
    await _make_user(session, "alice", "hunter2")
    result = await login(session, "alice", "nope", user_agent="ua", ip="1.2.3.4")
    assert result is None


@pytest.mark.asyncio
async def test_login_fails_for_inactive_user(session):
    user = await _make_user(session, "alice", "hunter2")
    user.is_active = False
    await session.commit()
    result = await login(session, "alice", "hunter2", user_agent="ua", ip="1.2.3.4")
    assert result is None


@pytest.mark.asyncio
async def test_lookup_session_returns_user(session):
    user = await _make_user(session, "alice", "hunter2")
    sess = await create_session(session, user, user_agent="ua", ip="1.2.3.4", ttl_minutes=60)
    await session.commit()
    looked = await lookup_session(session, sess.id)
    assert looked is not None
    assert looked.username == "alice"


@pytest.mark.asyncio
async def test_lookup_session_returns_none_for_unknown(session):
    looked = await lookup_session(session, "no-such-session")
    assert looked is None


@pytest.mark.asyncio
async def test_end_session_deletes_row(session):
    user = await _make_user(session, "alice", "hunter2")
    sess = await create_session(session, user, user_agent="ua", ip="1.2.3.4", ttl_minutes=60)
    await session.commit()
    await end_session(session, sess.id)
    await session.commit()
    rows = (await session.execute(select(Session))).scalars().all()
    assert rows == []
