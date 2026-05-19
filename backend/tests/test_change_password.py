from datetime import UTC, datetime

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from halite.auth.cookies import CookieCodec
from halite.auth.models import Session, User
from halite.auth.password import hash_password, verify_password
from halite.auth.service import create_session
from halite.config import Settings
from halite.main import create_app


async def _user(session, username="alice", password="oldpw-fine"):
    u = User(
        username_lower=username.lower(), username=username,
        password_hash=hash_password(password),
        is_active=True, must_change_pw=True,
        created_at=datetime.now(tz=UTC),
    )
    session.add(u)
    await session.commit()
    await session.refresh(u)
    return u


def _settings(app_db):
    return Settings(database_url=app_db, cookie_secret="x" * 64, cookie_secure=False)


@pytest.mark.asyncio
async def test_change_password_succeeds_with_current_password(app_db, session):
    settings = _settings(app_db)
    codec = CookieCodec(settings.cookie_secret)
    user = await _user(session)
    sess = await create_session(session, user, user_agent="ua", ip="1.2.3.4", ttl_minutes=60)
    await session.commit()
    app = create_app(settings=settings, codec=codec)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
        r = await ac.post(
            "/api/auth/change-password",
            json={"current_password": "oldpw-fine", "new_password": "newpw-fine"},
            cookies={settings.cookie_name: codec.sign(sess.id)},
        )
    assert r.status_code == 204
    await session.refresh(user)
    assert verify_password(user.password_hash, "newpw-fine")
    assert user.must_change_pw is False


@pytest.mark.asyncio
async def test_change_password_rejects_wrong_current(app_db, session):
    settings = _settings(app_db)
    codec = CookieCodec(settings.cookie_secret)
    user = await _user(session)
    sess = await create_session(session, user, user_agent="ua", ip="1.2.3.4", ttl_minutes=60)
    await session.commit()
    app = create_app(settings=settings, codec=codec)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
        r = await ac.post(
            "/api/auth/change-password",
            json={"current_password": "WRONG", "new_password": "newpw-fine"},
            cookies={settings.cookie_name: codec.sign(sess.id)},
        )
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_change_password_keeps_current_session_revokes_others(app_db, session):
    settings = _settings(app_db)
    codec = CookieCodec(settings.cookie_secret)
    user = await _user(session)
    keep = await create_session(session, user, user_agent="cur", ip="1.2.3.4", ttl_minutes=60)
    other = await create_session(session, user, user_agent="oth", ip="5.6.7.8", ttl_minutes=60)
    await session.commit()
    app = create_app(settings=settings, codec=codec)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
        r = await ac.post(
            "/api/auth/change-password",
            json={"current_password": "oldpw-fine", "new_password": "newpw-fine"},
            cookies={settings.cookie_name: codec.sign(keep.id)},
        )
    assert r.status_code == 204
    remaining_ids = {
        s.id for s in (
            await session.execute(select(Session).where(Session.user_id == user.id))
        ).scalars().all()
    }
    assert keep.id in remaining_ids
    assert other.id not in remaining_ids
