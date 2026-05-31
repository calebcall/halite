import pytest
from httpx import ASGITransport, AsyncClient

from halite.auth.cookies import CookieCodec
from halite.bootstrap import bootstrap_admin
from halite.config import Settings
from halite.demo import seed_demo
from halite.main import create_app
from halite.rbac.seed import seed_builtin_roles


def _settings(app_db, *, demo: bool):
    return Settings(database_url=app_db, cookie_secret="x" * 64, cookie_secure=False,
                    demo_mode=demo, demo_admin_password="s3cret-admin")


def _app(settings):
    return create_app(settings=settings, codec=CookieCodec(settings.cookie_secret))


@pytest.mark.asyncio
async def test_demo_login_issues_session(app_db, session):
    await seed_builtin_roles(session); await session.commit()
    await bootstrap_admin(session); await session.commit()
    await seed_demo(session, _settings(app_db, demo=True)); await session.commit()
    settings = _settings(app_db, demo=True)
    app = _app(settings)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
        r = await ac.post("/api/auth/demo-login")
        assert r.status_code == 200
        assert r.json()["username"] == "demo"
        cookie = r.cookies[settings.cookie_name]
        me = await ac.get("/api/auth/me", cookies={settings.cookie_name: cookie})
    assert me.status_code == 200 and me.json()["username"] == "demo"


@pytest.mark.asyncio
async def test_demo_login_404_when_not_demo(app_db, session):
    settings = _settings(app_db, demo=False)
    app = _app(settings)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
        r = await ac.post("/api/auth/demo-login")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_change_password_blocked_in_demo(app_db, session):
    await seed_builtin_roles(session); await session.commit()
    await bootstrap_admin(session); await session.commit()
    settings = _settings(app_db, demo=True)
    await seed_demo(session, settings); await session.commit()
    app = _app(settings)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
        login = await ac.post("/api/auth/login",
                              json={"username": "admin", "password": "s3cret-admin"})
        cookie = login.cookies[settings.cookie_name]
        r = await ac.post("/api/auth/change-password",
                          json={"current_password": "s3cret-admin", "new_password": "whatever123"},
                          cookies={settings.cookie_name: cookie})
    assert r.status_code == 403
