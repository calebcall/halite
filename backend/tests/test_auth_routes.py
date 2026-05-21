from datetime import UTC, datetime

import pytest
from httpx import ASGITransport, AsyncClient

from halite.auth.cookies import CookieCodec
from halite.auth.models import User
from halite.auth.password import hash_password
from halite.config import Settings
from halite.main import create_app


async def _make_user(session, username="alice", password="pw"):
    u = User(
        username_lower=username.lower(),
        username=username,
        password_hash=hash_password(password),
        is_active=True,
        created_at=datetime.now(tz=UTC),
    )
    session.add(u)
    await session.commit()
    return u


def _client(app_db):
    settings = Settings(database_url=app_db, cookie_secret="x" * 64, cookie_secure=False)
    codec = CookieCodec(settings.cookie_secret)
    return create_app(settings=settings, codec=codec), settings


@pytest.mark.asyncio
async def test_login_sets_cookie_and_returns_user(app_db, session):
    await _make_user(session)
    app, settings = _client(app_db)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
        r = await ac.post("/api/auth/login", json={"username": "alice", "password": "pw"})
    assert r.status_code == 200
    assert r.json()["username"] == "alice"
    assert settings.cookie_name in r.cookies


@pytest.mark.asyncio
async def test_login_401_on_bad_password(app_db, session):
    await _make_user(session)
    app, _ = _client(app_db)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
        r = await ac.post("/api/auth/login", json={"username": "alice", "password": "nope"})
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_me_returns_current_user(app_db, session):
    await _make_user(session)
    app, settings = _client(app_db)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
        login = await ac.post("/api/auth/login", json={"username": "alice", "password": "pw"})
        cookie = login.cookies[settings.cookie_name]
        me = await ac.get("/api/auth/me", cookies={settings.cookie_name: cookie})
    assert me.status_code == 200
    assert me.json()["username"] == "alice"


@pytest.mark.asyncio
async def test_logout_clears_cookie_and_invalidates_session(app_db, session):
    await _make_user(session)
    app, settings = _client(app_db)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
        login = await ac.post("/api/auth/login", json={"username": "alice", "password": "pw"})
        cookie = login.cookies[settings.cookie_name]
        out = await ac.post("/api/auth/logout", cookies={settings.cookie_name: cookie})
        me = await ac.get("/api/auth/me", cookies={settings.cookie_name: cookie})
    assert out.status_code == 204
    assert me.status_code == 401


@pytest.mark.asyncio
async def test_me_returns_permissions(app_db, session):
    """/api/auth/me must include the user's permissions array for the frontend
    to drive permission-aware UI gating."""
    from halite.rbac.models import Permission, Role, UserRole

    settings = Settings(database_url=app_db, cookie_secret="x" * 64, cookie_secure=False)
    codec = CookieCodec(settings.cookie_secret)

    user = User(
        username_lower="alice",
        username="alice",
        password_hash=hash_password("pw"),
        is_active=True,
        created_at=datetime.now(tz=UTC),
    )
    session.add(user)
    await session.flush()
    role = Role(name="ops", is_builtin=False, description="")
    session.add(role)
    await session.flush()
    session.add(Permission(role_id=role.id, verb="view", resource_glob="audit:*"))
    session.add(Permission(role_id=role.id, verb="run", resource_glob="state.*"))
    session.add(UserRole(user_id=user.id, role_id=role.id))
    await session.commit()
    await session.refresh(user)

    from halite.auth.service import create_session
    sess = await create_session(session, user, user_agent="ua", ip="1.2.3.4", ttl_minutes=60)
    await session.commit()

    app = create_app(settings=settings, codec=codec)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
        r = await ac.get("/api/auth/me", cookies={settings.cookie_name: codec.sign(sess.id)})
    assert r.status_code == 200
    body = r.json()
    assert body["username"] == "alice"
    perms = body["permissions"]
    assert isinstance(perms, list)
    pairs = {(p["verb"], p["resource_glob"]) for p in perms}
    assert ("view", "audit:*") in pairs
    assert ("run", "state.*") in pairs
