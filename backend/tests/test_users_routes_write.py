# backend/tests/test_users_routes_write.py
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


async def _admin_user(session, verbs_resources: list[tuple[str, str]]) -> User:
    user = User(
        username_lower="root", username="root",
        password_hash=hash_password("pw"),
        is_active=True, created_at=datetime.now(tz=UTC),
    )
    session.add(user)
    await session.flush()
    role = Role(name="admin-test", is_builtin=False, description="")
    session.add(role)
    await session.flush()
    for verb, glob in verbs_resources:
        session.add(Permission(role_id=role.id, verb=verb, resource_glob=glob))
    session.add(UserRole(user_id=user.id, role_id=role.id))
    await session.commit()
    await session.refresh(user)
    return user


def _client(app_db):
    settings = Settings(database_url=app_db, cookie_secret="x" * 64, cookie_secure=False)
    return create_app(settings=settings, codec=CookieCodec(settings.cookie_secret)), settings


@pytest.mark.asyncio
async def test_create_user_requires_manage_user_permission(app_db, session):
    settings = Settings(database_url=app_db, cookie_secret="x" * 64, cookie_secure=False)
    codec = CookieCodec(settings.cookie_secret)
    user = await _admin_user(session, [("view", "user:*")])  # view only
    sess = await create_session(session, user, user_agent="ua", ip="1.2.3.4", ttl_minutes=60)
    await session.commit()
    app = create_app(settings=settings, codec=codec)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
        r = await ac.post(
            "/api/users",
            json={"username": "alice", "password": "hunter2-strong"},
            cookies={settings.cookie_name: codec.sign(sess.id)},
        )
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_create_user_succeeds_for_admin(app_db, session):
    settings = Settings(database_url=app_db, cookie_secret="x" * 64, cookie_secure=False)
    codec = CookieCodec(settings.cookie_secret)
    admin = await _admin_user(session, [("manage_user", "user:*")])
    sess = await create_session(session, admin, user_agent="ua", ip="1.2.3.4", ttl_minutes=60)
    await session.commit()
    app = create_app(settings=settings, codec=codec)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
        r = await ac.post(
            "/api/users",
            json={"username": "alice", "password": "hunter2-strong"},
            cookies={settings.cookie_name: codec.sign(sess.id)},
        )
    assert r.status_code == 201
    body = r.json()
    assert body["username"] == "alice"
    assert body["must_change_pw"] is True


@pytest.mark.asyncio
async def test_create_user_409_on_duplicate(app_db, session):
    settings = Settings(database_url=app_db, cookie_secret="x" * 64, cookie_secure=False)
    codec = CookieCodec(settings.cookie_secret)
    admin = await _admin_user(session, [("manage_user", "user:*")])
    sess = await create_session(session, admin, user_agent="ua", ip="1.2.3.4", ttl_minutes=60)
    await session.commit()
    app = create_app(settings=settings, codec=codec)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
        cookies = {settings.cookie_name: codec.sign(sess.id)}
        first = await ac.post(
            "/api/users",
            json={"username": "alice", "password": "hunter2-strong"},
            cookies=cookies,
        )
        second = await ac.post(
            "/api/users",
            json={"username": "ALICE", "password": "hunter2-strong"},
            cookies=cookies,
        )
    assert first.status_code == 201
    assert second.status_code == 409


@pytest.mark.asyncio
async def test_create_user_writes_audit_with_redacted_password(app_db, session):
    settings = Settings(database_url=app_db, cookie_secret="x" * 64, cookie_secure=False)
    codec = CookieCodec(settings.cookie_secret)
    admin = await _admin_user(session, [("manage_user", "user:*")])
    sess = await create_session(session, admin, user_agent="ua", ip="1.2.3.4", ttl_minutes=60)
    await session.commit()
    app = create_app(settings=settings, codec=codec)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
        r = await ac.post(
            "/api/users",
            json={"username": "alice", "password": "hunter2-strong"},
            cookies={settings.cookie_name: codec.sign(sess.id)},
        )
    assert r.status_code == 201
    rows = (
        await session.execute(
            select(AuditEntry).where(AuditEntry.action == "user.create")
        )
    ).scalars().all()
    assert len(rows) == 1
    assert rows[0].args_json["password"] == "[REDACTED]"
    assert rows[0].decision == "allow"


@pytest.mark.asyncio
async def test_update_user_changes_display_name(app_db, session):
    settings = Settings(database_url=app_db, cookie_secret="x" * 64, cookie_secure=False)
    codec = CookieCodec(settings.cookie_secret)
    admin = await _admin_user(session, [("manage_user", "user:*")])
    sess = await create_session(session, admin, user_agent="ua", ip="1.2.3.4", ttl_minutes=60)
    await session.commit()
    app = create_app(settings=settings, codec=codec)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
        cookies = {settings.cookie_name: codec.sign(sess.id)}
        created = await ac.post(
            "/api/users", json={"username": "alice", "password": "hunter2-strong"}, cookies=cookies
        )
        user_id = created.json()["id"]
        upd = await ac.patch(
            f"/api/users/{user_id}", json={"display_name": "Alice Smith"}, cookies=cookies
        )
    assert upd.status_code == 200
    assert upd.json()["display_name"] == "Alice Smith"


@pytest.mark.asyncio
async def test_update_user_404_for_unknown(app_db, session):
    import uuid
    settings = Settings(database_url=app_db, cookie_secret="x" * 64, cookie_secure=False)
    codec = CookieCodec(settings.cookie_secret)
    admin = await _admin_user(session, [("manage_user", "user:*")])
    sess = await create_session(session, admin, user_agent="ua", ip="1.2.3.4", ttl_minutes=60)
    await session.commit()
    app = create_app(settings=settings, codec=codec)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
        r = await ac.patch(
            f"/api/users/{uuid.uuid4()}",
            json={"display_name": "X"},
            cookies={settings.cookie_name: codec.sign(sess.id)},
        )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_delete_user_204(app_db, session):
    settings = Settings(database_url=app_db, cookie_secret="x" * 64, cookie_secure=False)
    codec = CookieCodec(settings.cookie_secret)
    admin = await _admin_user(session, [("manage_user", "user:*")])
    sess = await create_session(session, admin, user_agent="ua", ip="1.2.3.4", ttl_minutes=60)
    await session.commit()
    app = create_app(settings=settings, codec=codec)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
        cookies = {settings.cookie_name: codec.sign(sess.id)}
        created = await ac.post(
            "/api/users", json={"username": "alice", "password": "hunter2-strong"}, cookies=cookies
        )
        user_id = created.json()["id"]
        d = await ac.delete(f"/api/users/{user_id}", cookies=cookies)
        check = await ac.get(f"/api/users/{user_id}", cookies=cookies)
    assert d.status_code == 204
    assert check.status_code == 404


@pytest.mark.asyncio
async def test_delete_user_409_on_self(app_db, session):
    settings = Settings(database_url=app_db, cookie_secret="x" * 64, cookie_secure=False)
    codec = CookieCodec(settings.cookie_secret)
    admin = await _admin_user(session, [("manage_user", "user:*")])
    sess = await create_session(session, admin, user_agent="ua", ip="1.2.3.4", ttl_minutes=60)
    await session.commit()
    app = create_app(settings=settings, codec=codec)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
        r = await ac.delete(
            f"/api/users/{admin.id}", cookies={settings.cookie_name: codec.sign(sess.id)}
        )
    assert r.status_code == 409


@pytest.mark.asyncio
async def test_delete_user_409_on_builtin(app_db, session):
    settings = Settings(database_url=app_db, cookie_secret="x" * 64, cookie_secure=False)
    codec = CookieCodec(settings.cookie_secret)
    admin = await _admin_user(session, [("manage_user", "user:*")])
    sess = await create_session(session, admin, user_agent="ua", ip="1.2.3.4", ttl_minutes=60)

    builtin = User(
        username_lower="builtin", username="builtin",
        password_hash=hash_password("pw"),
        is_active=True, is_builtin=True, created_at=datetime.now(tz=UTC),
    )
    session.add(builtin)
    await session.commit()
    app = create_app(settings=settings, codec=codec)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
        r = await ac.delete(
            f"/api/users/{builtin.id}", cookies={settings.cookie_name: codec.sign(sess.id)}
        )
    assert r.status_code == 409
