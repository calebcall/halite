# backend/tests/test_user_roles.py
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


async def _admin_target_role(session):
    admin = User(
        username_lower="root", username="root",
        password_hash=hash_password("pw"),
        is_active=True, created_at=datetime.now(tz=UTC),
    )
    session.add(admin)
    await session.flush()
    admin_role = Role(name="admin-test", is_builtin=False, description="")
    session.add(admin_role)
    await session.flush()
    session.add(Permission(role_id=admin_role.id, verb="manage_user", resource_glob="user:*"))
    session.add(UserRole(user_id=admin.id, role_id=admin_role.id))

    target_user = User(
        username_lower="alice", username="alice",
        password_hash=hash_password("pw"),
        is_active=True, created_at=datetime.now(tz=UTC),
    )
    session.add(target_user)
    grantable = Role(name="ops", is_builtin=False, description="")
    session.add(grantable)
    await session.commit()
    await session.refresh(admin)
    await session.refresh(target_user)
    await session.refresh(grantable)
    return admin, target_user, grantable


@pytest.mark.asyncio
async def test_list_user_roles_empty(app_db, session):
    settings = Settings(database_url=app_db, cookie_secret="x" * 64, cookie_secure=False)
    codec = CookieCodec(settings.cookie_secret)
    admin, target, _ = await _admin_target_role(session)
    # admin also needs view:user:* for this GET test
    role_id = (
        await session.execute(select(Role.id).where(Role.name == "admin-test"))
    ).scalar_one()
    session.add(Permission(role_id=role_id, verb="view", resource_glob="user:*"))
    sess = await create_session(session, admin, user_agent="ua", ip="1.2.3.4", ttl_minutes=60)
    await session.commit()
    app = create_app(settings=settings, codec=codec)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
        r = await ac.get(
            f"/api/users/{target.id}/roles", cookies={settings.cookie_name: codec.sign(sess.id)}
        )
    assert r.status_code == 200
    assert r.json() == []


@pytest.mark.asyncio
async def test_add_user_role_creates_link(app_db, session):
    settings = Settings(database_url=app_db, cookie_secret="x" * 64, cookie_secure=False)
    codec = CookieCodec(settings.cookie_secret)
    admin, target, grantable = await _admin_target_role(session)
    sess = await create_session(session, admin, user_agent="ua", ip="1.2.3.4", ttl_minutes=60)
    await session.commit()
    app = create_app(settings=settings, codec=codec)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
        r = await ac.post(
            f"/api/users/{target.id}/roles",
            json={"role_id": str(grantable.id)},
            cookies={settings.cookie_name: codec.sign(sess.id)},
        )
    assert r.status_code == 201
    link = (await session.execute(
        select(UserRole).where(UserRole.user_id == target.id, UserRole.role_id == grantable.id)
    )).scalar_one_or_none()
    assert link is not None


@pytest.mark.asyncio
async def test_add_user_role_idempotent(app_db, session):
    settings = Settings(database_url=app_db, cookie_secret="x" * 64, cookie_secure=False)
    codec = CookieCodec(settings.cookie_secret)
    admin, target, grantable = await _admin_target_role(session)
    sess = await create_session(session, admin, user_agent="ua", ip="1.2.3.4", ttl_minutes=60)
    await session.commit()
    app = create_app(settings=settings, codec=codec)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
        cookies = {settings.cookie_name: codec.sign(sess.id)}
        a = await ac.post(
            f"/api/users/{target.id}/roles", json={"role_id": str(grantable.id)}, cookies=cookies
        )
        b = await ac.post(
            f"/api/users/{target.id}/roles", json={"role_id": str(grantable.id)}, cookies=cookies
        )
    assert a.status_code == 201
    assert b.status_code == 200  # 200 = already assigned, no-op


@pytest.mark.asyncio
async def test_remove_user_role(app_db, session):
    settings = Settings(database_url=app_db, cookie_secret="x" * 64, cookie_secure=False)
    codec = CookieCodec(settings.cookie_secret)
    admin, target, grantable = await _admin_target_role(session)
    sess = await create_session(session, admin, user_agent="ua", ip="1.2.3.4", ttl_minutes=60)
    session.add(UserRole(user_id=target.id, role_id=grantable.id))
    await session.commit()
    app = create_app(settings=settings, codec=codec)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
        d = await ac.delete(
            f"/api/users/{target.id}/roles/{grantable.id}",
            cookies={settings.cookie_name: codec.sign(sess.id)},
        )
    assert d.status_code == 204
    link = (await session.execute(
        select(UserRole).where(UserRole.user_id == target.id, UserRole.role_id == grantable.id)
    )).scalar_one_or_none()
    assert link is None
