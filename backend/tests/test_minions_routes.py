# backend/tests/test_minions_routes.py
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
from halite.salt.client import SaltAPIClient


async def _viewer(session) -> User:
    user = User(
        username_lower="alice",
        username="alice",
        password_hash=hash_password("pw"),
        is_active=True,
        created_at=datetime.now(tz=UTC),
    )
    session.add(user)
    await session.flush()
    role = Role(name="viewer-test", is_builtin=False, description="")
    session.add(role)
    await session.flush()
    session.add(Permission(role_id=role.id, verb="view", resource_glob="minion:*"))
    session.add(UserRole(user_id=user.id, role_id=role.id))
    await session.commit()
    await session.refresh(user)
    return user


async def _user_without_view(session) -> User:
    user = User(
        username_lower="bob",
        username="bob",
        password_hash=hash_password("pw"),
        is_active=True,
        created_at=datetime.now(tz=UTC),
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


@pytest.mark.asyncio
async def test_minions_503_when_salt_not_configured(app_db, session):
    """When SALT_API_URL is unset, /api/minions returns 503."""
    settings = Settings(database_url=app_db, cookie_secret="x" * 64, cookie_secure=False)
    codec = CookieCodec(settings.cookie_secret)
    user = await _viewer(session)
    sess = await create_session(session, user, user_agent="ua", ip="1.2.3.4", ttl_minutes=60)
    await session.commit()

    app = create_app(settings=settings, codec=codec)
    async with (
        AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac,
        app.router.lifespan_context(app),
    ):
        r = await ac.get("/api/minions", cookies={settings.cookie_name: codec.sign(sess.id)})
    assert r.status_code == 503
    assert "not configured" in r.json()["detail"].lower()


@pytest.mark.asyncio
async def test_minions_403_without_permission(app_db, session, fake_salt_api):
    settings = Settings(
        database_url=app_db,
        cookie_secret="x" * 64,
        cookie_secure=False,
        salt_api_url="http://salt.test",
        salt_api_username="halite-service",
        salt_api_password="pw",
    )
    codec = CookieCodec(settings.cookie_secret)
    user = await _user_without_view(session)
    sess = await create_session(session, user, user_agent="ua", ip="1.2.3.4", ttl_minutes=60)
    await session.commit()

    app = create_app(settings=settings, codec=codec)

    # Pre-populate app.state.salt_client with a SaltAPIClient bound to the fake transport,
    # so the route gets past the 503 check.
    app.state.salt_client = SaltAPIClient(
        base_url="http://salt.test",
        username="halite-service",
        password="pw",
        transport=fake_salt_api.transport,
    )
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
            r = await ac.get(
                "/api/minions", cookies={settings.cookie_name: codec.sign(sess.id)}
            )
    finally:
        await app.state.salt_client.aclose()
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_minions_list_returns_connected(app_db, session, fake_salt_api):
    settings = Settings(database_url=app_db, cookie_secret="x" * 64, cookie_secure=False)
    codec = CookieCodec(settings.cookie_secret)
    user = await _viewer(session)
    sess = await create_session(session, user, user_agent="ua", ip="1.2.3.4", ttl_minutes=60)
    await session.commit()

    fake_salt_api.run_handler = lambda payload: {
        "return": [{"data": {"return": {"web-01": "10.0.0.1", "db-01": "10.0.0.2"}}}]
    }

    app = create_app(settings=settings, codec=codec)
    app.state.salt_client = SaltAPIClient(
        base_url="http://salt.test",
        username="halite-service",
        password="pw",
        transport=fake_salt_api.transport,
    )
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
            r = await ac.get(
                "/api/minions", cookies={settings.cookie_name: codec.sign(sess.id)}
            )
    finally:
        await app.state.salt_client.aclose()
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 2
    ids = [m["id"] for m in body["minions"]]
    assert ids == ["db-01", "web-01"]  # sorted alphabetically
