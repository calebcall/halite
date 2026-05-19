from datetime import UTC, datetime

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from halite.auth.cookies import CookieCodec
from halite.auth.models import User
from halite.auth.password import hash_password
from halite.auth.service import create_session
from halite.config import Settings
from halite.deps import CurrentUser


def _build_app(settings: Settings, codec: CookieCodec) -> FastAPI:
    from halite.main import create_app as _create_app
    app = _create_app(settings=settings, codec=codec)

    @app.get("/whoami")
    async def whoami(user: CurrentUser):
        return {"username": user.username}

    return app


@pytest.mark.asyncio
async def test_current_user_returns_user_for_valid_cookie(app_db, session):
    settings = Settings(database_url=app_db, cookie_secret="x" * 64, cookie_secure=False)
    codec = CookieCodec(settings.cookie_secret)

    user = User(
        username_lower="alice",
        username="alice",
        password_hash=hash_password("pw"),
        is_active=True,
        created_at=datetime.now(tz=UTC),
    )
    session.add(user)
    await session.commit()
    sess = await create_session(session, user, user_agent="ua", ip="1.2.3.4", ttl_minutes=60)
    await session.commit()

    app = _build_app(settings, codec)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
        cookie = codec.sign(sess.id)
        r = await ac.get("/whoami", cookies={settings.cookie_name: cookie})
    assert r.status_code == 200
    assert r.json() == {"username": "alice"}


@pytest.mark.asyncio
async def test_current_user_401_without_cookie(app_db):
    settings = Settings(database_url=app_db, cookie_secret="x" * 64, cookie_secure=False)
    codec = CookieCodec(settings.cookie_secret)
    app = _build_app(settings, codec)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
        r = await ac.get("/whoami")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_current_user_401_with_tampered_cookie(app_db):
    settings = Settings(database_url=app_db, cookie_secret="x" * 64, cookie_secure=False)
    codec = CookieCodec(settings.cookie_secret)
    app = _build_app(settings, codec)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
        r = await ac.get("/whoami", cookies={settings.cookie_name: "definitely-not-signed"})
    assert r.status_code == 401
