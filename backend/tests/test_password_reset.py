# backend/tests/test_password_reset.py
from datetime import UTC, datetime

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from halite.auth.cookies import CookieCodec
from halite.auth.models import Session, User
from halite.auth.password import hash_password, verify_password
from halite.auth.service import create_session
from halite.config import Settings
from halite.main import create_app
from halite.rbac.models import Permission, Role, UserRole


async def _admin_and_target(session):
    admin = User(
        username_lower="root", username="root",
        password_hash=hash_password("pw"),
        is_active=True, created_at=datetime.now(tz=UTC),
    )
    session.add(admin)
    await session.flush()
    role = Role(name="admin-test", is_builtin=False, description="")
    session.add(role)
    await session.flush()
    session.add(Permission(role_id=role.id, verb="manage_user", resource_glob="user:*"))
    session.add(UserRole(user_id=admin.id, role_id=role.id))

    target = User(
        username_lower="bob", username="bob",
        password_hash=hash_password("oldpw"),
        is_active=True, must_change_pw=False, created_at=datetime.now(tz=UTC),
    )
    session.add(target)
    await session.commit()
    await session.refresh(admin)
    await session.refresh(target)
    return admin, target


@pytest.mark.asyncio
async def test_admin_can_reset_password_and_revokes_sessions(app_db, session):
    settings = Settings(database_url=app_db, cookie_secret="x" * 64, cookie_secure=False)
    codec = CookieCodec(settings.cookie_secret)
    admin, target = await _admin_and_target(session)
    admin_sess = await create_session(session, admin, user_agent="ua", ip="1.2.3.4", ttl_minutes=60)
    await create_session(session, target, user_agent="ua", ip="1.2.3.4", ttl_minutes=60)
    await session.commit()

    app = create_app(settings=settings, codec=codec)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
        r = await ac.post(
            f"/api/users/{target.id}/password",
            json={"new_password": "brandnew-12345", "must_change_pw": True},
            cookies={settings.cookie_name: codec.sign(admin_sess.id)},
        )
    assert r.status_code == 204

    # password updated
    await session.refresh(target)
    assert verify_password(target.password_hash, "brandnew-12345")
    assert target.must_change_pw is True

    # target's session revoked
    remaining = (
        await session.execute(select(Session).where(Session.user_id == target.id))
    ).scalars().all()
    assert remaining == []


@pytest.mark.asyncio
async def test_password_reset_audit_redacts(app_db, session):
    from halite.audit.models import AuditEntry
    settings = Settings(database_url=app_db, cookie_secret="x" * 64, cookie_secure=False)
    codec = CookieCodec(settings.cookie_secret)
    admin, target = await _admin_and_target(session)
    admin_sess = await create_session(session, admin, user_agent="ua", ip="1.2.3.4", ttl_minutes=60)
    await session.commit()
    app = create_app(settings=settings, codec=codec)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
        await ac.post(
            f"/api/users/{target.id}/password",
            json={"new_password": "brandnew-12345", "must_change_pw": True},
            cookies={settings.cookie_name: codec.sign(admin_sess.id)},
        )
    rows = (
        await session.execute(select(AuditEntry).where(AuditEntry.action == "user.password_reset"))
    ).scalars().all()
    assert len(rows) == 1
    assert rows[0].args_json["new_password"] == "[REDACTED]"
