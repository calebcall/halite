from __future__ import annotations

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
    role = Role(name="viewer-db-test", is_builtin=False, description="")
    session.add(role)
    await session.flush()
    session.add(Permission(role_id=role.id, verb="view", resource_glob="minion:*"))
    session.add(UserRole(user_id=user.id, role_id=role.id))
    await session.commit()
    await session.refresh(user)
    return user


@pytest.mark.asyncio
async def test_list_minions_empty_db_returns_zero_total(app_db, session):
    settings = Settings(database_url=app_db, cookie_secret="x" * 64, cookie_secure=False)
    codec = CookieCodec(settings.cookie_secret)
    user = await _viewer(session)
    sess = await create_session(session, user, user_agent="ua", ip="1.2.3.4", ttl_minutes=60)
    await session.commit()

    app = create_app(settings=settings, codec=codec)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
        r = await ac.get("/api/minions", cookies={settings.cookie_name: codec.sign(sess.id)})

    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 0
    assert body["minions"] == []
    assert body["last_refreshed_at"] is None
    assert body["is_stale"] is False


@pytest.mark.asyncio
async def test_list_minions_returns_seeded_rows_with_freshness(app_db, session):
    settings = Settings(database_url=app_db, cookie_secret="x" * 64, cookie_secure=False)
    codec = CookieCodec(settings.cookie_secret)
    user = await _viewer(session)
    sess = await create_session(session, user, user_agent="ua", ip="1.2.3.4", ttl_minutes=60)
    now = datetime.now(tz=UTC)
    session.add(MinionSnapshot(
        minion_id="web-1",
        key_status="accepted",
        online=True,
        primary_ip="10.0.0.1",
        os="Ubuntu",
        os_family="Debian",
        osrelease="22.04",
        saltversion="3006.5",
        keys_refreshed_at=now,
        presence_refreshed_at=now,
        grains_refreshed_at=now,
    ))
    session.add(MinionSnapshot(
        minion_id="db-1",
        key_status="accepted",
        online=False,
        keys_refreshed_at=now,
        presence_refreshed_at=now,
    ))
    await session.commit()

    app = create_app(settings=settings, codec=codec)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
        r = await ac.get("/api/minions", cookies={settings.cookie_name: codec.sign(sess.id)})

    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 2
    by_id = {m["id"]: m for m in body["minions"]}
    assert by_id["web-1"]["status"] == "online"
    assert by_id["web-1"]["os"] == "Ubuntu"
    assert by_id["db-1"]["status"] == "offline"
    assert body["last_refreshed_at"] is not None
    assert body["is_stale"] is False


@pytest.mark.asyncio
async def test_list_minions_status_derives_from_key_status_and_online(app_db, session):
    settings = Settings(database_url=app_db, cookie_secret="x" * 64, cookie_secure=False)
    codec = CookieCodec(settings.cookie_secret)
    user = await _viewer(session)
    sess = await create_session(session, user, user_agent="ua", ip="1.2.3.4", ttl_minutes=60)
    now = datetime.now(tz=UTC)
    session.add(MinionSnapshot(
        minion_id="a",
        key_status="accepted",
        online=True,
        keys_refreshed_at=now,
        presence_refreshed_at=now,
    ))
    session.add(MinionSnapshot(
        minion_id="b",
        key_status="accepted",
        online=False,
        keys_refreshed_at=now,
        presence_refreshed_at=now,
    ))
    session.add(MinionSnapshot(
        minion_id="c",
        key_status="pending",
        online=False,
        keys_refreshed_at=now,
    ))
    session.add(MinionSnapshot(
        minion_id="d",
        key_status="rejected",
        online=False,
        keys_refreshed_at=now,
    ))
    await session.commit()

    app = create_app(settings=settings, codec=codec)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
        r = await ac.get("/api/minions", cookies={settings.cookie_name: codec.sign(sess.id)})

    by_id = {m["id"]: m["status"] for m in r.json()["minions"]}
    assert by_id == {"a": "online", "b": "offline", "c": "pending", "d": "rejected"}


@pytest.mark.asyncio
async def test_get_minion_returns_grains_and_freshness(app_db, session):
    settings = Settings(database_url=app_db, cookie_secret="x" * 64, cookie_secure=False)
    codec = CookieCodec(settings.cookie_secret)
    user = await _viewer(session)
    sess = await create_session(session, user, user_agent="ua", ip="1.2.3.4", ttl_minutes=60)
    now = datetime.now(tz=UTC)
    session.add(MinionSnapshot(
        minion_id="web-1",
        key_status="accepted",
        online=True,
        primary_ip="10.0.0.1",
        os="Ubuntu",
        grains={"os": "Ubuntu", "kernel": "Linux", "ip4_interfaces": {"eth0": ["10.0.0.1"]}},
        keys_refreshed_at=now,
        presence_refreshed_at=now,
        grains_refreshed_at=now,
    ))
    await session.commit()

    app = create_app(settings=settings, codec=codec)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
        r = await ac.get("/api/minions/web-1", cookies={settings.cookie_name: codec.sign(sess.id)})

    assert r.status_code == 200
    body = r.json()
    assert body["id"] == "web-1"
    assert body["status"] == "online"
    assert body["ip"] == "10.0.0.1"
    assert body["grains"]["os"] == "Ubuntu"
    assert body["is_stale"] is False
    assert body["last_refreshed_at"] is not None


@pytest.mark.asyncio
async def test_get_minion_404_when_unknown(app_db, session):
    settings = Settings(database_url=app_db, cookie_secret="x" * 64, cookie_secure=False)
    codec = CookieCodec(settings.cookie_secret)
    user = await _viewer(session)
    sess = await create_session(session, user, user_agent="ua", ip="1.2.3.4", ttl_minutes=60)
    await session.commit()

    app = create_app(settings=settings, codec=codec)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
        r = await ac.get(
            "/api/minions/does-not-exist",
            cookies={settings.cookie_name: codec.sign(sess.id)},
        )

    assert r.status_code == 404
