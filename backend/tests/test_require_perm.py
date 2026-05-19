from datetime import UTC, datetime

import pytest
from httpx import ASGITransport, AsyncClient

from halite.auth.cookies import CookieCodec
from halite.auth.models import User
from halite.auth.password import hash_password
from halite.auth.service import create_session
from halite.config import Settings
from halite.deps import require_perm
from halite.rbac.models import Permission, Role, UserRole


def _build_app(settings, codec):
    from halite.main import create_app as _create_app
    app = _create_app(settings=settings, codec=codec)

    @app.get("/secret", dependencies=[require_perm("view", "audit:*")])
    async def secret():
        return {"ok": True}

    return app


async def _user_with_perm(session, perms: list[tuple[str, str]]) -> User:
    user = User(
        username_lower="alice",
        username="alice",
        password_hash=hash_password("pw"),
        is_active=True,
        created_at=datetime.now(tz=UTC),
    )
    session.add(user)
    await session.flush()
    role = Role(name="test", is_builtin=False, description="")
    session.add(role)
    await session.flush()
    for verb, glob in perms:
        session.add(Permission(role_id=role.id, verb=verb, resource_glob=glob))
    session.add(UserRole(user_id=user.id, role_id=role.id))
    await session.commit()
    await session.refresh(user)
    return user


@pytest.mark.asyncio
async def test_require_perm_allows_when_user_has_matching_perm(app_db, session):
    settings = Settings(database_url=app_db, cookie_secret="x" * 64, cookie_secure=False)
    codec = CookieCodec(settings.cookie_secret)
    user = await _user_with_perm(session, [("view", "audit:*")])
    sess = await create_session(session, user, user_agent="ua", ip="1.2.3.4", ttl_minutes=60)
    await session.commit()

    app = _build_app(settings, codec)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
        r = await ac.get(
            "/secret", cookies={settings.cookie_name: codec.sign(sess.id)}
        )
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_require_perm_denies_without_matching_perm(app_db, session):
    settings = Settings(database_url=app_db, cookie_secret="x" * 64, cookie_secure=False)
    codec = CookieCodec(settings.cookie_secret)
    user = await _user_with_perm(session, [("view", "minion:*")])
    sess = await create_session(session, user, user_agent="ua", ip="1.2.3.4", ttl_minutes=60)
    await session.commit()

    app = _build_app(settings, codec)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
        r = await ac.get(
            "/secret", cookies={settings.cookie_name: codec.sign(sess.id)}
        )
    assert r.status_code == 403
