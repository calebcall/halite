# backend/tests/test_keys_routes.py
from datetime import UTC, datetime

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from halite.audit.models import AuditEntry
from halite.auth.cookies import CookieCodec
from halite.auth.models import User
from halite.auth.password import hash_password
from halite.auth.service import create_session
from halite.config import Settings
from halite.main import create_app
from halite.rbac.models import Permission, Role, UserRole
from halite.salt.client import SaltAPIClient


async def _user_with(session, perms: list[tuple[str, str]]) -> User:
    user = User(
        username_lower="alice",
        username="alice",
        password_hash=hash_password("pw"),
        is_active=True,
        created_at=datetime.now(tz=UTC),
    )
    session.add(user)
    await session.flush()
    role = Role(name="keys-test", is_builtin=False, description="")
    session.add(role)
    await session.flush()
    for verb, glob in perms:
        session.add(Permission(role_id=role.id, verb=verb, resource_glob=glob))
    session.add(UserRole(user_id=user.id, role_id=role.id))
    await session.commit()
    await session.refresh(user)
    return user


def _attach_salt_client(app, fake_salt_api) -> SaltAPIClient:
    client = SaltAPIClient(
        base_url="http://salt.test",
        username="halite-service",
        password="pw",
        transport=fake_salt_api.transport,
    )
    app.state.salt_client = client
    return client


def _key_list_handler(buckets: dict[str, list[str]]):
    """Handler that responds to key.list_all with the given buckets and to any
    other wheel call with a generic success response."""
    full = {
        "minions": [],
        "minions_pre": [],
        "minions_rejected": [],
        "minions_denied": [],
        "local": [],
    }
    full.update(buckets)

    def handler(payload):
        fun = payload.get("fun", "")
        if fun == "key.list_all":
            return {"return": [{"data": {"return": full}}]}
        return {"return": [{"data": {"return": {"minions": [payload.get("match")]}, "success": True}}]}

    return handler


# ---------- List ----------


@pytest.mark.asyncio
async def test_keys_list_returns_status_per_key(app_db, session, fake_salt_api):
    settings = Settings(database_url=app_db, cookie_secret="x" * 64, cookie_secure=False)
    codec = CookieCodec(settings.cookie_secret)
    user = await _user_with(session, [("view", "key:*")])
    sess = await create_session(session, user, user_agent="ua", ip="1.2.3.4", ttl_minutes=60)
    await session.commit()

    fake_salt_api.run_handler = _key_list_handler({
        "minions": ["web-01"],
        "minions_pre": ["pending-host"],
        "minions_rejected": ["bad-host"],
        "minions_denied": ["spoofed"],
    })

    app = create_app(settings=settings, codec=codec)
    client = _attach_salt_client(app, fake_salt_api)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
            r = await ac.get("/api/keys", cookies={settings.cookie_name: codec.sign(sess.id)})
    finally:
        await client.aclose()

    assert r.status_code == 200
    body = r.json()
    by_id = {k["id"]: k["status"] for k in body["keys"]}
    assert by_id == {
        "web-01": "accepted",
        "pending-host": "pending",
        "bad-host": "rejected",
        "spoofed": "denied",
    }


@pytest.mark.asyncio
async def test_keys_list_403_without_view_key(app_db, session, fake_salt_api):
    settings = Settings(database_url=app_db, cookie_secret="x" * 64, cookie_secure=False)
    codec = CookieCodec(settings.cookie_secret)
    user = await _user_with(session, [("view", "minion:*")])
    sess = await create_session(session, user, user_agent="ua", ip="1.2.3.4", ttl_minutes=60)
    await session.commit()

    fake_salt_api.run_handler = _key_list_handler({})

    app = create_app(settings=settings, codec=codec)
    client = _attach_salt_client(app, fake_salt_api)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
            r = await ac.get("/api/keys", cookies={settings.cookie_name: codec.sign(sess.id)})
    finally:
        await client.aclose()
    assert r.status_code == 403


# ---------- Mutations ----------


@pytest.mark.asyncio
async def test_accept_key_204_and_audit(app_db, session, fake_salt_api):
    settings = Settings(database_url=app_db, cookie_secret="x" * 64, cookie_secure=False)
    codec = CookieCodec(settings.cookie_secret)
    user = await _user_with(session, [("accept", "key:*")])
    sess = await create_session(session, user, user_agent="ua", ip="1.2.3.4", ttl_minutes=60)
    await session.commit()

    fake_salt_api.run_handler = _key_list_handler({})

    app = create_app(settings=settings, codec=codec)
    client = _attach_salt_client(app, fake_salt_api)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
            r = await ac.post(
                "/api/keys/pending-host/accept",
                cookies={settings.cookie_name: codec.sign(sess.id)},
            )
    finally:
        await client.aclose()
    assert r.status_code == 204

    rows = (
        await session.execute(select(AuditEntry).where(AuditEntry.action == "key.accept"))
    ).scalars().all()
    assert len(rows) == 1
    assert rows[0].resource == "key:pending-host"
    assert rows[0].decision == "allow"


@pytest.mark.asyncio
async def test_reject_key_403_without_perm(app_db, session, fake_salt_api):
    settings = Settings(database_url=app_db, cookie_secret="x" * 64, cookie_secure=False)
    codec = CookieCodec(settings.cookie_secret)
    user = await _user_with(session, [("view", "key:*")])
    sess = await create_session(session, user, user_agent="ua", ip="1.2.3.4", ttl_minutes=60)
    await session.commit()

    fake_salt_api.run_handler = _key_list_handler({})

    app = create_app(settings=settings, codec=codec)
    client = _attach_salt_client(app, fake_salt_api)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
            r = await ac.post(
                "/api/keys/web-01/reject",
                cookies={settings.cookie_name: codec.sign(sess.id)},
            )
    finally:
        await client.aclose()
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_delete_key_204(app_db, session, fake_salt_api):
    settings = Settings(database_url=app_db, cookie_secret="x" * 64, cookie_secure=False)
    codec = CookieCodec(settings.cookie_secret)
    user = await _user_with(session, [("delete", "key:*")])
    sess = await create_session(session, user, user_agent="ua", ip="1.2.3.4", ttl_minutes=60)
    await session.commit()

    fake_salt_api.run_handler = _key_list_handler({})

    app = create_app(settings=settings, codec=codec)
    client = _attach_salt_client(app, fake_salt_api)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
            r = await ac.delete(
                "/api/keys/web-01",
                cookies={settings.cookie_name: codec.sign(sess.id)},
            )
    finally:
        await client.aclose()
    assert r.status_code == 204

    rows = (
        await session.execute(select(AuditEntry).where(AuditEntry.action == "key.delete"))
    ).scalars().all()
    assert len(rows) == 1
    assert rows[0].resource == "key:web-01"
    assert rows[0].decision == "allow"


@pytest.mark.asyncio
async def test_reject_key_204_and_audit(app_db, session, fake_salt_api):
    settings = Settings(database_url=app_db, cookie_secret="x" * 64, cookie_secure=False)
    codec = CookieCodec(settings.cookie_secret)
    user = await _user_with(session, [("reject", "key:*")])
    sess = await create_session(session, user, user_agent="ua", ip="1.2.3.4", ttl_minutes=60)
    await session.commit()

    fake_salt_api.run_handler = _key_list_handler({})

    app = create_app(settings=settings, codec=codec)
    client = _attach_salt_client(app, fake_salt_api)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
            r = await ac.post(
                "/api/keys/bad-host/reject",
                cookies={settings.cookie_name: codec.sign(sess.id)},
            )
    finally:
        await client.aclose()
    assert r.status_code == 204

    rows = (
        await session.execute(select(AuditEntry).where(AuditEntry.action == "key.reject"))
    ).scalars().all()
    assert len(rows) == 1
    assert rows[0].resource == "key:bad-host"
    assert rows[0].decision == "allow"


@pytest.mark.asyncio
async def test_keys_list_503_when_salt_not_configured(app_db, session):
    settings = Settings(database_url=app_db, cookie_secret="x" * 64, cookie_secure=False)
    codec = CookieCodec(settings.cookie_secret)
    user = await _user_with(session, [("view", "key:*")])
    sess = await create_session(session, user, user_agent="ua", ip="1.2.3.4", ttl_minutes=60)
    await session.commit()

    app = create_app(settings=settings, codec=codec)
    async with (
        AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac,
        app.router.lifespan_context(app),
    ):
        r = await ac.get("/api/keys", cookies={settings.cookie_name: codec.sign(sess.id)})
    assert r.status_code == 503
