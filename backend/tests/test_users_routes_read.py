# backend/tests/test_users_routes_read.py
from datetime import UTC, datetime

import pytest
from httpx import ASGITransport, AsyncClient

from halite.auth.cookies import CookieCodec
from halite.auth.models import User
from halite.auth.password import hash_password
from halite.auth.service import create_session
from halite.config import Settings
from halite.main import create_app
from halite.rbac.models import Permission, Role, UserRole


async def _user_with_perms(session, perms: list[tuple[str, str]]) -> User:
    user = User(
        username_lower="alice", username="alice",
        password_hash=hash_password("pw"),
        is_active=True, created_at=datetime.now(tz=UTC),
    )
    session.add(user)
    await session.flush()
    role = Role(name="test-role", is_builtin=False, description="")
    session.add(role)
    await session.flush()
    for verb, glob in perms:
        session.add(Permission(role_id=role.id, verb=verb, resource_glob=glob))
    session.add(UserRole(user_id=user.id, role_id=role.id))
    await session.commit()
    await session.refresh(user)
    return user


def _client(app_db):
    settings = Settings(database_url=app_db, cookie_secret="x" * 64, cookie_secure=False)
    return create_app(settings=settings, codec=CookieCodec(settings.cookie_secret)), settings


@pytest.mark.asyncio
async def test_list_users_requires_auth(app_db):
    app, _ = _client(app_db)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
        r = await ac.get("/api/users")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_list_users_requires_permission(app_db, session):
    settings = Settings(database_url=app_db, cookie_secret="x" * 64, cookie_secure=False)
    codec = CookieCodec(settings.cookie_secret)
    user = await _user_with_perms(session, [("view", "audit:*")])  # no user:* perm
    sess = await create_session(session, user, user_agent="ua", ip="1.2.3.4", ttl_minutes=60)
    await session.commit()
    app = create_app(settings=settings, codec=codec)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
        r = await ac.get("/api/users", cookies={settings.cookie_name: codec.sign(sess.id)})
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_list_users_returns_summary(app_db, session):
    settings = Settings(database_url=app_db, cookie_secret="x" * 64, cookie_secure=False)
    codec = CookieCodec(settings.cookie_secret)
    user = await _user_with_perms(session, [("view", "user:*")])
    sess = await create_session(session, user, user_agent="ua", ip="1.2.3.4", ttl_minutes=60)
    await session.commit()
    app = create_app(settings=settings, codec=codec)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
        r = await ac.get("/api/users", cookies={settings.cookie_name: codec.sign(sess.id)})
    assert r.status_code == 200
    body = r.json()
    assert body["total"] >= 1
    assert any(u["username"] == "alice" for u in body["users"])


@pytest.mark.asyncio
async def test_get_user_returns_one(app_db, session):
    settings = Settings(database_url=app_db, cookie_secret="x" * 64, cookie_secure=False)
    codec = CookieCodec(settings.cookie_secret)
    user = await _user_with_perms(session, [("view", "user:*")])
    sess = await create_session(session, user, user_agent="ua", ip="1.2.3.4", ttl_minutes=60)
    await session.commit()
    app = create_app(settings=settings, codec=codec)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
        r = await ac.get(f"/api/users/{user.id}", cookies={settings.cookie_name: codec.sign(sess.id)})
    assert r.status_code == 200
    assert r.json()["username"] == "alice"


@pytest.mark.asyncio
async def test_get_user_404_for_unknown(app_db, session):
    import uuid
    settings = Settings(database_url=app_db, cookie_secret="x" * 64, cookie_secure=False)
    codec = CookieCodec(settings.cookie_secret)
    user = await _user_with_perms(session, [("view", "user:*")])
    sess = await create_session(session, user, user_agent="ua", ip="1.2.3.4", ttl_minutes=60)
    await session.commit()
    app = create_app(settings=settings, codec=codec)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
        r = await ac.get(
            f"/api/users/{uuid.uuid4()}", cookies={settings.cookie_name: codec.sign(sess.id)}
        )
    assert r.status_code == 404
