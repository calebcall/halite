from datetime import UTC, datetime, timedelta

import pytest
from httpx import ASGITransport, AsyncClient

from halite.audit.models import AuditEntry
from halite.auth.cookies import CookieCodec
from halite.auth.models import User
from halite.auth.password import hash_password
from halite.auth.service import create_session
from halite.config import Settings
from halite.main import create_app
from halite.rbac.models import Permission, Role, UserRole


async def _user_with_audit_view(session) -> User:
    user = User(
        username_lower="alice", username="alice",
        password_hash=hash_password("pw"),
        is_active=True, created_at=datetime.now(tz=UTC),
    )
    session.add(user)
    await session.flush()
    role = Role(name="auditor", is_builtin=False, description="")
    session.add(role)
    await session.flush()
    session.add(Permission(role_id=role.id, verb="view", resource_glob="audit:*"))
    session.add(UserRole(user_id=user.id, role_id=role.id))
    await session.commit()
    await session.refresh(user)
    return user


@pytest.mark.asyncio
async def test_audit_list_requires_auth(app_db):
    settings = Settings(database_url=app_db, cookie_secret="x" * 64, cookie_secure=False)
    app = create_app(settings=settings, codec=CookieCodec(settings.cookie_secret))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
        r = await ac.get("/api/audit")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_audit_list_requires_permission(app_db, session):
    settings = Settings(database_url=app_db, cookie_secret="x" * 64, cookie_secure=False)
    codec = CookieCodec(settings.cookie_secret)

    user = User(
        username_lower="bob", username="bob",
        password_hash=hash_password("pw"),
        is_active=True, created_at=datetime.now(tz=UTC),
    )
    session.add(user)
    await session.commit()
    sess = await create_session(session, user, user_agent="ua", ip="1.2.3.4", ttl_minutes=60)
    await session.commit()

    app = create_app(settings=settings, codec=codec)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
        r = await ac.get("/api/audit", cookies={settings.cookie_name: codec.sign(sess.id)})
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_audit_list_returns_rows_with_filters(app_db, session):
    settings = Settings(database_url=app_db, cookie_secret="x" * 64, cookie_secure=False)
    codec = CookieCodec(settings.cookie_secret)
    user = await _user_with_audit_view(session)
    sess = await create_session(session, user, user_agent="ua", ip="1.2.3.4", ttl_minutes=60)

    now = datetime.now(tz=UTC)
    session.add(AuditEntry(at=now, user_id=user.id, action="auth.login", resource="user:alice",
                           args_json=None, salt_jid=None, decision="allow", result_code=200))
    session.add(AuditEntry(at=now - timedelta(minutes=1), user_id=user.id, action="salt.run",
                           resource="minion:web-01", args_json=None, salt_jid="J1",
                           decision="allow", result_code=200))
    session.add(AuditEntry(at=now - timedelta(minutes=2), user_id=user.id, action="salt.run",
                           resource="minion:db-01", args_json=None, salt_jid="J2",
                           decision="deny", result_code=403))
    await session.commit()

    app = create_app(settings=settings, codec=codec)
    cookies = {settings.cookie_name: codec.sign(sess.id)}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
        all_r = await ac.get("/api/audit", cookies=cookies)
        action_r = await ac.get("/api/audit?action=salt.run", cookies=cookies)
        deny_r = await ac.get("/api/audit?decision=deny", cookies=cookies)

    assert all_r.status_code == 200
    body = all_r.json()
    assert body["total"] >= 3
    assert [e["action"] for e in body["entries"][:1]] == ["auth.login"]

    assert all(e["action"] == "salt.run" for e in action_r.json()["entries"])
    assert all(e["decision"] == "deny" for e in deny_r.json()["entries"])
