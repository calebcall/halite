# backend/tests/test_minions_routes.py
"""Route-level tests for /api/minions and /api/minions/{id}.

The minions routes read from the MinionSnapshot DB table (populated by the
MinionStateScheduler). They do not call salt-api directly, so there is no
fake_salt_api wiring here. Behaviour is verified by seeding MinionSnapshot
rows and asserting the API response.

Detailed DB-service coverage lives in test_minion_db_routes.py; this file
focuses on auth/permission guards and basic response shapes at the route layer.
"""

from datetime import UTC, datetime

import pytest
from httpx import ASGITransport, AsyncClient

from halite.auth.cookies import CookieCodec
from halite.auth.models import User
from halite.auth.password import hash_password
from halite.auth.service import create_session
from halite.config import Settings
from halite.main import create_app
from halite.minions.snapshot_model import MinionSnapshot
from halite.rbac.models import Permission, Role, UserRole


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


# ---------- List endpoint ----------


@pytest.mark.asyncio
async def test_minions_returns_empty_list_when_salt_not_configured(app_db, session):
    """The minions list route reads from the DB — it does not require a live
    salt-api connection, so it returns 200 with an empty list when unconfigured."""
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
    assert r.status_code == 200
    assert r.json()["total"] == 0


@pytest.mark.asyncio
async def test_minions_403_without_permission(app_db, session):
    settings = Settings(database_url=app_db, cookie_secret="x" * 64, cookie_secure=False)
    codec = CookieCodec(settings.cookie_secret)
    user = await _user_without_view(session)
    sess = await create_session(session, user, user_agent="ua", ip="1.2.3.4", ttl_minutes=60)
    await session.commit()

    app = create_app(settings=settings, codec=codec)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
        r = await ac.get("/api/minions", cookies={settings.cookie_name: codec.sign(sess.id)})
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_minions_list_returns_status_per_minion(app_db, session):
    """List returns one entry per MinionSnapshot row with correct status fields."""
    settings = Settings(database_url=app_db, cookie_secret="x" * 64, cookie_secure=False)
    codec = CookieCodec(settings.cookie_secret)
    user = await _viewer(session)
    sess = await create_session(session, user, user_agent="ua", ip="1.2.3.4", ttl_minutes=60)
    now = datetime.now(tz=UTC)

    session.add(MinionSnapshot(
        minion_id="web-01",
        key_status="accepted",
        online=True,
        primary_ip="10.0.0.1",
        keys_refreshed_at=now,
        presence_refreshed_at=now,
    ))
    session.add(MinionSnapshot(
        minion_id="db-01",
        key_status="accepted",
        online=False,
        keys_refreshed_at=now,
        presence_refreshed_at=now,
    ))
    session.add(MinionSnapshot(
        minion_id="new-host",
        key_status="pending",
        online=False,
        keys_refreshed_at=now,
    ))
    session.add(MinionSnapshot(
        minion_id="bad-host",
        key_status="rejected",
        online=False,
        keys_refreshed_at=now,
    ))
    await session.commit()

    app = create_app(settings=settings, codec=codec)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
        r = await ac.get("/api/minions", cookies={settings.cookie_name: codec.sign(sess.id)})

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
async def test_minion_detail_online_returns_grains(app_db, session):
    settings = Settings(database_url=app_db, cookie_secret="x" * 64, cookie_secure=False)
    codec = CookieCodec(settings.cookie_secret)
    user = await _viewer(session)
    sess = await create_session(session, user, user_agent="ua", ip="1.2.3.4", ttl_minutes=60)
    now = datetime.now(tz=UTC)

    session.add(MinionSnapshot(
        minion_id="web-01",
        key_status="accepted",
        online=True,
        primary_ip="10.0.0.1",
        grains={"os": "Ubuntu", "kernel": "Linux"},
        keys_refreshed_at=now,
        presence_refreshed_at=now,
        grains_refreshed_at=now,
    ))
    await session.commit()

    app = create_app(settings=settings, codec=codec)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
        r = await ac.get(
            "/api/minions/web-01", cookies={settings.cookie_name: codec.sign(sess.id)}
        )

    assert r.status_code == 200
    body = r.json()
    assert body["id"] == "web-01"
    assert body["status"] == "online"
    assert body["ip"] == "10.0.0.1"
    assert body["grains"] == {"os": "Ubuntu", "kernel": "Linux"}


@pytest.mark.asyncio
async def test_minion_detail_offline_omits_grains(app_db, session):
    settings = Settings(database_url=app_db, cookie_secret="x" * 64, cookie_secure=False)
    codec = CookieCodec(settings.cookie_secret)
    user = await _viewer(session)
    sess = await create_session(session, user, user_agent="ua", ip="1.2.3.4", ttl_minutes=60)
    now = datetime.now(tz=UTC)

    session.add(MinionSnapshot(
        minion_id="db-01",
        key_status="accepted",
        online=False,
        keys_refreshed_at=now,
        presence_refreshed_at=now,
    ))
    await session.commit()

    app = create_app(settings=settings, codec=codec)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
        r = await ac.get(
            "/api/minions/db-01", cookies={settings.cookie_name: codec.sign(sess.id)}
        )

    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "offline"
    assert body["grains"] is None
    assert body["ip"] is None


@pytest.mark.asyncio
async def test_minion_detail_pending(app_db, session):
    settings = Settings(database_url=app_db, cookie_secret="x" * 64, cookie_secure=False)
    codec = CookieCodec(settings.cookie_secret)
    user = await _viewer(session)
    sess = await create_session(session, user, user_agent="ua", ip="1.2.3.4", ttl_minutes=60)
    now = datetime.now(tz=UTC)

    session.add(MinionSnapshot(
        minion_id="new-host",
        key_status="pending",
        online=False,
        keys_refreshed_at=now,
    ))
    await session.commit()

    app = create_app(settings=settings, codec=codec)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
        r = await ac.get(
            "/api/minions/new-host", cookies={settings.cookie_name: codec.sign(sess.id)}
        )

    assert r.status_code == 200
    assert r.json()["status"] == "pending"


@pytest.mark.asyncio
async def test_minion_detail_404(app_db, session):
    settings = Settings(database_url=app_db, cookie_secret="x" * 64, cookie_secure=False)
    codec = CookieCodec(settings.cookie_secret)
    user = await _viewer(session)
    sess = await create_session(session, user, user_agent="ua", ip="1.2.3.4", ttl_minutes=60)
    await session.commit()

    app = create_app(settings=settings, codec=codec)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
        r = await ac.get(
            "/api/minions/ghost", cookies={settings.cookie_name: codec.sign(sess.id)}
        )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_minion_detail_404_when_salt_not_configured(app_db, session):
    """Detail route reads from DB — salt unconfigured means no rows, so 404."""
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
    assert r.status_code == 404
