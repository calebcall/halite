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


def _attach_salt_client(app, fake_salt_api) -> SaltAPIClient:
    """Construct a SaltAPIClient with the fake transport and attach it to app.state."""
    client = SaltAPIClient(
        base_url="http://salt.test",
        username="halite-service",
        password="pw",
        transport=fake_salt_api.transport,
    )
    app.state.salt_client = client
    return client


def _salt_router(
    connected: dict[str, str] | None = None,
    keys: dict[str, list[str]] | None = None,
    grains: dict[str, dict | None] | None = None,
):
    """Returns a run_handler that responds to wheel/local calls based on the
    payload's `fun` field. Pass dicts for the data this test cares about."""
    connected = connected or {}
    keys = keys or {"minions": [], "minions_pre": [], "minions_rejected": [], "minions_denied": [], "local": []}
    grains = grains or {}

    def handler(payload):
        fun = payload.get("fun", "")
        if fun == "minions.connected":
            return {"return": [{"data": {"return": connected}}]}
        if fun == "key.list_all":
            return {"return": [{"data": {"return": keys}}]}
        if fun == "grains.items":
            target = payload.get("tgt", "")
            return {"return": [{target: grains.get(target)} if target in grains else {}]}
        return {"return": [None]}

    return handler


# ---------- List endpoint ----------


@pytest.mark.asyncio
async def test_minions_503_when_salt_not_configured(app_db, session):
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


@pytest.mark.asyncio
async def test_minions_403_without_permission(app_db, session, fake_salt_api):
    settings = Settings(database_url=app_db, cookie_secret="x" * 64, cookie_secure=False)
    codec = CookieCodec(settings.cookie_secret)
    user = await _user_without_view(session)
    sess = await create_session(session, user, user_agent="ua", ip="1.2.3.4", ttl_minutes=60)
    await session.commit()

    app = create_app(settings=settings, codec=codec)
    client = _attach_salt_client(app, fake_salt_api)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
            r = await ac.get("/api/minions", cookies={settings.cookie_name: codec.sign(sess.id)})
    finally:
        await client.aclose()
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_minions_list_returns_status_per_minion(app_db, session, fake_salt_api):
    settings = Settings(database_url=app_db, cookie_secret="x" * 64, cookie_secure=False)
    codec = CookieCodec(settings.cookie_secret)
    user = await _viewer(session)
    sess = await create_session(session, user, user_agent="ua", ip="1.2.3.4", ttl_minutes=60)
    await session.commit()

    fake_salt_api.run_handler = _salt_router(
        connected={"web-01": "10.0.0.1"},
        keys={
            "minions": ["web-01", "db-01"],
            "minions_pre": ["new-host"],
            "minions_rejected": ["bad-host"],
            "minions_denied": [],
            "local": [],
        },
    )

    app = create_app(settings=settings, codec=codec)
    client = _attach_salt_client(app, fake_salt_api)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
            r = await ac.get("/api/minions", cookies={settings.cookie_name: codec.sign(sess.id)})
    finally:
        await client.aclose()

    assert r.status_code == 200
    body = r.json()
    by_id = {m["id"]: m for m in body["minions"]}
    assert body["total"] == 4
    assert by_id["web-01"]["status"] == "online"
    assert by_id["web-01"]["ip"] == "10.0.0.1"
    assert by_id["db-01"]["status"] == "offline"
    assert by_id["db-01"]["ip"] is None
    assert by_id["new-host"]["status"] == "pending"
    assert by_id["bad-host"]["status"] == "rejected"


# ---------- Detail endpoint ----------


@pytest.mark.asyncio
async def test_minion_detail_online_returns_grains(app_db, session, fake_salt_api):
    settings = Settings(database_url=app_db, cookie_secret="x" * 64, cookie_secure=False)
    codec = CookieCodec(settings.cookie_secret)
    user = await _viewer(session)
    sess = await create_session(session, user, user_agent="ua", ip="1.2.3.4", ttl_minutes=60)
    await session.commit()

    fake_salt_api.run_handler = _salt_router(
        connected={"web-01": "10.0.0.1"},
        keys={"minions": ["web-01"], "minions_pre": [], "minions_rejected": [], "minions_denied": [], "local": []},
        grains={"web-01": {"os": "Ubuntu", "kernel": "Linux"}},
    )

    app = create_app(settings=settings, codec=codec)
    client = _attach_salt_client(app, fake_salt_api)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
            r = await ac.get("/api/minions/web-01", cookies={settings.cookie_name: codec.sign(sess.id)})
    finally:
        await client.aclose()

    assert r.status_code == 200
    body = r.json()
    assert body == {
        "id": "web-01",
        "status": "online",
        "ip": "10.0.0.1",
        "grains": {"os": "Ubuntu", "kernel": "Linux"},
    }


@pytest.mark.asyncio
async def test_minion_detail_offline_omits_grains(app_db, session, fake_salt_api):
    settings = Settings(database_url=app_db, cookie_secret="x" * 64, cookie_secure=False)
    codec = CookieCodec(settings.cookie_secret)
    user = await _viewer(session)
    sess = await create_session(session, user, user_agent="ua", ip="1.2.3.4", ttl_minutes=60)
    await session.commit()

    fake_salt_api.run_handler = _salt_router(
        connected={},
        keys={"minions": ["db-01"], "minions_pre": [], "minions_rejected": [], "minions_denied": [], "local": []},
    )

    app = create_app(settings=settings, codec=codec)
    client = _attach_salt_client(app, fake_salt_api)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
            r = await ac.get("/api/minions/db-01", cookies={settings.cookie_name: codec.sign(sess.id)})
    finally:
        await client.aclose()

    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "offline"
    assert body["grains"] is None
    assert body["ip"] is None


@pytest.mark.asyncio
async def test_minion_detail_pending(app_db, session, fake_salt_api):
    settings = Settings(database_url=app_db, cookie_secret="x" * 64, cookie_secure=False)
    codec = CookieCodec(settings.cookie_secret)
    user = await _viewer(session)
    sess = await create_session(session, user, user_agent="ua", ip="1.2.3.4", ttl_minutes=60)
    await session.commit()

    fake_salt_api.run_handler = _salt_router(
        connected={},
        keys={"minions": [], "minions_pre": ["new-host"], "minions_rejected": [], "minions_denied": [], "local": []},
    )

    app = create_app(settings=settings, codec=codec)
    client = _attach_salt_client(app, fake_salt_api)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
            r = await ac.get("/api/minions/new-host", cookies={settings.cookie_name: codec.sign(sess.id)})
    finally:
        await client.aclose()

    assert r.status_code == 200
    assert r.json()["status"] == "pending"


@pytest.mark.asyncio
async def test_minion_detail_404(app_db, session, fake_salt_api):
    settings = Settings(database_url=app_db, cookie_secret="x" * 64, cookie_secure=False)
    codec = CookieCodec(settings.cookie_secret)
    user = await _viewer(session)
    sess = await create_session(session, user, user_agent="ua", ip="1.2.3.4", ttl_minutes=60)
    await session.commit()

    fake_salt_api.run_handler = _salt_router(
        connected={}, keys={"minions": [], "minions_pre": [], "minions_rejected": [], "minions_denied": [], "local": []},
    )

    app = create_app(settings=settings, codec=codec)
    client = _attach_salt_client(app, fake_salt_api)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
            r = await ac.get("/api/minions/ghost", cookies={settings.cookie_name: codec.sign(sess.id)})
    finally:
        await client.aclose()
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_minion_detail_503_when_salt_not_configured(app_db, session):
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
        r = await ac.get("/api/minions/web-01", cookies={settings.cookie_name: codec.sign(sess.id)})
    assert r.status_code == 503
