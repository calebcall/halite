# backend/tests/test_roles_routes.py
from datetime import UTC, datetime

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from halite.auth.cookies import CookieCodec
from halite.auth.models import User
from halite.auth.password import hash_password
from halite.auth.service import create_session
from halite.config import Settings
from halite.main import create_app
from halite.rbac.models import Permission, Role, UserRole


async def _admin(session) -> User:
    u = User(
        username_lower="root", username="root",
        password_hash=hash_password("pw"),
        is_active=True, created_at=datetime.now(tz=UTC),
    )
    session.add(u)
    await session.flush()
    r = Role(name="admin-test", is_builtin=False, description="")
    session.add(r)
    await session.flush()
    session.add(Permission(role_id=r.id, verb="manage_role", resource_glob="role:*"))
    session.add(Permission(role_id=r.id, verb="view", resource_glob="role:*"))
    session.add(UserRole(user_id=u.id, role_id=r.id))
    await session.commit()
    await session.refresh(u)
    return u


@pytest.mark.asyncio
async def test_list_roles(app_db, session):
    settings = Settings(database_url=app_db, cookie_secret="x" * 64, cookie_secure=False)
    codec = CookieCodec(settings.cookie_secret)
    admin = await _admin(session)
    sess = await create_session(session, admin, user_agent="ua", ip="1.2.3.4", ttl_minutes=60)
    await session.commit()
    app = create_app(settings=settings, codec=codec)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
        r = await ac.get("/api/roles", cookies={settings.cookie_name: codec.sign(sess.id)})
    assert r.status_code == 200
    assert r.json()["total"] >= 1


@pytest.mark.asyncio
async def test_get_role_includes_permissions(app_db, session):
    settings = Settings(database_url=app_db, cookie_secret="x" * 64, cookie_secure=False)
    codec = CookieCodec(settings.cookie_secret)
    admin = await _admin(session)
    sess = await create_session(session, admin, user_agent="ua", ip="1.2.3.4", ttl_minutes=60)
    role = (await session.execute(select(Role).where(Role.name == "admin-test"))).scalar_one()
    await session.commit()
    app = create_app(settings=settings, codec=codec)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
        r = await ac.get(
            f"/api/roles/{role.id}", cookies={settings.cookie_name: codec.sign(sess.id)}
        )
    assert r.status_code == 200
    body = r.json()
    assert body["name"] == "admin-test"
    assert len(body["permissions"]) == 2


@pytest.mark.asyncio
async def test_create_role(app_db, session):
    settings = Settings(database_url=app_db, cookie_secret="x" * 64, cookie_secure=False)
    codec = CookieCodec(settings.cookie_secret)
    admin = await _admin(session)
    sess = await create_session(session, admin, user_agent="ua", ip="1.2.3.4", ttl_minutes=60)
    await session.commit()
    app = create_app(settings=settings, codec=codec)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
        r = await ac.post(
            "/api/roles",
            json={"name": "ops", "description": "Ops team"},
            cookies={settings.cookie_name: codec.sign(sess.id)},
        )
    assert r.status_code == 201
    assert r.json()["name"] == "ops"


@pytest.mark.asyncio
async def test_create_role_409_on_duplicate(app_db, session):
    settings = Settings(database_url=app_db, cookie_secret="x" * 64, cookie_secure=False)
    codec = CookieCodec(settings.cookie_secret)
    admin = await _admin(session)
    sess = await create_session(session, admin, user_agent="ua", ip="1.2.3.4", ttl_minutes=60)
    await session.commit()
    app = create_app(settings=settings, codec=codec)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
        cookies = {settings.cookie_name: codec.sign(sess.id)}
        await ac.post("/api/roles", json={"name": "ops"}, cookies=cookies)
        r = await ac.post("/api/roles", json={"name": "ops"}, cookies=cookies)
    assert r.status_code == 409


@pytest.mark.asyncio
async def test_update_role(app_db, session):
    settings = Settings(database_url=app_db, cookie_secret="x" * 64, cookie_secure=False)
    codec = CookieCodec(settings.cookie_secret)
    admin = await _admin(session)
    sess = await create_session(session, admin, user_agent="ua", ip="1.2.3.4", ttl_minutes=60)
    await session.commit()
    app = create_app(settings=settings, codec=codec)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
        cookies = {settings.cookie_name: codec.sign(sess.id)}
        created = await ac.post("/api/roles", json={"name": "ops"}, cookies=cookies)
        rid = created.json()["id"]
        upd = await ac.patch(f"/api/roles/{rid}", json={"description": "New"}, cookies=cookies)
    assert upd.status_code == 200
    assert upd.json()["description"] == "New"


@pytest.mark.asyncio
async def test_delete_role(app_db, session):
    settings = Settings(database_url=app_db, cookie_secret="x" * 64, cookie_secure=False)
    codec = CookieCodec(settings.cookie_secret)
    admin = await _admin(session)
    sess = await create_session(session, admin, user_agent="ua", ip="1.2.3.4", ttl_minutes=60)
    await session.commit()
    app = create_app(settings=settings, codec=codec)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
        cookies = {settings.cookie_name: codec.sign(sess.id)}
        created = await ac.post("/api/roles", json={"name": "ops"}, cookies=cookies)
        rid = created.json()["id"]
        d = await ac.delete(f"/api/roles/{rid}", cookies=cookies)
        check = await ac.get(f"/api/roles/{rid}", cookies=cookies)
    assert d.status_code == 204
    assert check.status_code == 404


@pytest.mark.asyncio
async def test_delete_builtin_role_409(app_db, session):
    settings = Settings(database_url=app_db, cookie_secret="x" * 64, cookie_secure=False)
    codec = CookieCodec(settings.cookie_secret)
    admin = await _admin(session)
    sess = await create_session(session, admin, user_agent="ua", ip="1.2.3.4", ttl_minutes=60)
    from halite.rbac.seed import seed_builtin_roles
    await seed_builtin_roles(session)
    await session.commit()
    admin_role = (await session.execute(select(Role).where(Role.name == "admin"))).scalar_one()
    app = create_app(settings=settings, codec=codec)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
        r = await ac.delete(
            f"/api/roles/{admin_role.id}", cookies={settings.cookie_name: codec.sign(sess.id)}
        )
    assert r.status_code == 409
