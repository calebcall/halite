# backend/tests/test_role_permissions.py
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


async def _admin_and_role(session):
    u = User(
        username_lower="root", username="root",
        password_hash=hash_password("pw"),
        is_active=True, created_at=datetime.now(tz=UTC),
    )
    session.add(u)
    await session.flush()
    admin_role = Role(name="admin-test", is_builtin=False, description="")
    session.add(admin_role)
    await session.flush()
    session.add(Permission(role_id=admin_role.id, verb="manage_role", resource_glob="role:*"))
    session.add(Permission(role_id=admin_role.id, verb="view", resource_glob="role:*"))
    session.add(UserRole(user_id=u.id, role_id=admin_role.id))

    target = Role(name="ops", is_builtin=False, description="")
    session.add(target)
    await session.commit()
    await session.refresh(u)
    await session.refresh(target)
    return u, target


@pytest.mark.asyncio
async def test_add_permission_creates_row(app_db, session):
    settings = Settings(database_url=app_db, cookie_secret="x" * 64, cookie_secure=False)
    codec = CookieCodec(settings.cookie_secret)
    admin, target = await _admin_and_role(session)
    sess = await create_session(session, admin, user_agent="ua", ip="1.2.3.4", ttl_minutes=60)
    await session.commit()
    app = create_app(settings=settings, codec=codec)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
        r = await ac.post(
            f"/api/roles/{target.id}/permissions",
            json={"verb": "run", "resource_glob": "state.*"},
            cookies={settings.cookie_name: codec.sign(sess.id)},
        )
    assert r.status_code == 201
    assert r.json()["verb"] == "run"


@pytest.mark.asyncio
async def test_delete_permission(app_db, session):
    settings = Settings(database_url=app_db, cookie_secret="x" * 64, cookie_secure=False)
    codec = CookieCodec(settings.cookie_secret)
    admin, target = await _admin_and_role(session)
    sess = await create_session(session, admin, user_agent="ua", ip="1.2.3.4", ttl_minutes=60)
    await session.commit()
    app = create_app(settings=settings, codec=codec)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
        cookies = {settings.cookie_name: codec.sign(sess.id)}
        created = await ac.post(
            f"/api/roles/{target.id}/permissions",
            json={"verb": "run", "resource_glob": "state.*"},
            cookies=cookies,
        )
        pid = created.json()["id"]
        d = await ac.delete(f"/api/roles/{target.id}/permissions/{pid}", cookies=cookies)
    assert d.status_code == 204


@pytest.mark.asyncio
async def test_delete_permission_404_when_wrong_role(app_db, session):
    settings = Settings(database_url=app_db, cookie_secret="x" * 64, cookie_secure=False)
    codec = CookieCodec(settings.cookie_secret)
    admin, target = await _admin_and_role(session)
    sess = await create_session(session, admin, user_agent="ua", ip="1.2.3.4", ttl_minutes=60)
    other = Role(name="other", is_builtin=False, description="")
    session.add(other)
    await session.commit()
    await session.refresh(other)
    app = create_app(settings=settings, codec=codec)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
        cookies = {settings.cookie_name: codec.sign(sess.id)}
        created = await ac.post(
            f"/api/roles/{target.id}/permissions",
            json={"verb": "run", "resource_glob": "state.*"},
            cookies=cookies,
        )
        pid = created.json()["id"]
        d = await ac.delete(f"/api/roles/{other.id}/permissions/{pid}", cookies=cookies)
    assert d.status_code == 404
