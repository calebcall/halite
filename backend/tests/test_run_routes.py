# backend/tests/test_run_routes.py
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
    role = Role(name="run-test", is_builtin=False, description="")
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


def _run_handler(jid: str = "20260123120000000000", minions: list[str] | None = None):
    def handler(payload):
        return {"return": [{"jid": jid, "minions": minions or ["web-01"]}]}
    return handler


@pytest.mark.asyncio
async def test_run_command_returns_jid_and_audits(app_db, session, fake_salt_api):
    settings = Settings(database_url=app_db, cookie_secret="x" * 64, cookie_secure=False)
    codec = CookieCodec(settings.cookie_secret)
    user = await _user_with(session, [("execute", "salt:*")])
    sess = await create_session(session, user, user_agent="ua", ip="1.2.3.4", ttl_minutes=60)
    await session.commit()

    fake_salt_api.run_handler = _run_handler(minions=["web-01", "web-02"])

    app = create_app(settings=settings, codec=codec)
    client = _attach_salt_client(app, fake_salt_api)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
            r = await ac.post(
                "/api/run",
                cookies={settings.cookie_name: codec.sign(sess.id)},
                json={"target": "web-*", "fun": "test.ping"},
            )
    finally:
        await client.aclose()

    assert r.status_code == 202
    body = r.json()
    assert body["jid"] == "20260123120000000000"
    assert body["minions"] == ["web-01", "web-02"]

    rows = (
        await session.execute(select(AuditEntry).where(AuditEntry.action == "salt.run"))
    ).scalars().all()
    assert len(rows) == 1
    assert rows[0].resource == "salt:test.ping"
    assert rows[0].decision == "allow"
    assert rows[0].salt_jid == "20260123120000000000"


@pytest.mark.asyncio
async def test_run_command_403_without_execute(app_db, session, fake_salt_api):
    settings = Settings(database_url=app_db, cookie_secret="x" * 64, cookie_secure=False)
    codec = CookieCodec(settings.cookie_secret)
    user = await _user_with(session, [("view", "job:*")])
    sess = await create_session(session, user, user_agent="ua", ip="1.2.3.4", ttl_minutes=60)
    await session.commit()

    fake_salt_api.run_handler = _run_handler()

    app = create_app(settings=settings, codec=codec)
    client = _attach_salt_client(app, fake_salt_api)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
            r = await ac.post(
                "/api/run",
                cookies={settings.cookie_name: codec.sign(sess.id)},
                json={"target": "web-*", "fun": "test.ping"},
            )
    finally:
        await client.aclose()
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_run_command_422_for_bad_fun(app_db, session, fake_salt_api):
    settings = Settings(database_url=app_db, cookie_secret="x" * 64, cookie_secure=False)
    codec = CookieCodec(settings.cookie_secret)
    user = await _user_with(session, [("execute", "salt:*")])
    sess = await create_session(session, user, user_agent="ua", ip="1.2.3.4", ttl_minutes=60)
    await session.commit()

    fake_salt_api.run_handler = _run_handler()

    app = create_app(settings=settings, codec=codec)
    client = _attach_salt_client(app, fake_salt_api)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
            r = await ac.post(
                "/api/run",
                cookies={settings.cookie_name: codec.sign(sess.id)},
                json={"target": "*", "fun": "nodot"},
            )
    finally:
        await client.aclose()
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_run_command_502_when_salt_returns_no_jid(app_db, session, fake_salt_api):
    settings = Settings(database_url=app_db, cookie_secret="x" * 64, cookie_secure=False)
    codec = CookieCodec(settings.cookie_secret)
    user = await _user_with(session, [("execute", "salt:*")])
    sess = await create_session(session, user, user_agent="ua", ip="1.2.3.4", ttl_minutes=60)
    await session.commit()

    def handler(payload):
        return {"return": [{}]}

    fake_salt_api.run_handler = handler

    app = create_app(settings=settings, codec=codec)
    client = _attach_salt_client(app, fake_salt_api)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
            r = await ac.post(
                "/api/run",
                cookies={settings.cookie_name: codec.sign(sess.id)},
                json={"target": "*", "fun": "test.ping"},
            )
    finally:
        await client.aclose()
    assert r.status_code == 502

    rows = (
        await session.execute(select(AuditEntry).where(AuditEntry.action == "salt.run"))
    ).scalars().all()
    assert len(rows) == 1
    assert rows[0].decision == "deny"
    assert rows[0].result_code == 502


@pytest.mark.asyncio
async def test_run_command_accepts_dict_kwarg_value(app_db, session, fake_salt_api):
    settings = Settings(database_url=app_db, cookie_secret="x" * 64, cookie_secure=False)
    codec = CookieCodec(settings.cookie_secret)
    user = await _user_with(session, [("execute", "salt:*")])
    sess = await create_session(session, user, user_agent="ua", ip="1.2.3.4", ttl_minutes=60)
    await session.commit()

    captured_kwarg: dict = {}

    def handler(payload):
        captured_kwarg.update(payload.get("kwarg") or {})
        return {"return": [{"jid": "20260123120000000001", "minions": ["web-01"]}]}

    fake_salt_api.run_handler = handler

    app = create_app(settings=settings, codec=codec)
    client = _attach_salt_client(app, fake_salt_api)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
            r = await ac.post(
                "/api/run",
                cookies={settings.cookie_name: codec.sign(sess.id)},
                json={
                    "target": "*",
                    "fun": "state.apply",
                    "args": ["mystate"],
                    "kwargs": {"pillar": {"env": "prod"}},
                },
            )
    finally:
        await client.aclose()
    assert r.status_code == 202
    assert captured_kwarg == {"pillar": {"env": "prod"}}


@pytest.mark.asyncio
async def test_run_command_503_when_salt_not_configured(app_db, session):
    settings = Settings(database_url=app_db, cookie_secret="x" * 64, cookie_secure=False)
    codec = CookieCodec(settings.cookie_secret)
    user = await _user_with(session, [("execute", "salt:*")])
    sess = await create_session(session, user, user_agent="ua", ip="1.2.3.4", ttl_minutes=60)
    await session.commit()

    app = create_app(settings=settings, codec=codec)
    async with (
        AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac,
        app.router.lifespan_context(app),
    ):
        r = await ac.post(
            "/api/run",
            cookies={settings.cookie_name: codec.sign(sess.id)},
            json={"target": "*", "fun": "test.ping"},
        )
    assert r.status_code == 503
