import pytest
from httpx import ASGITransport, AsyncClient

from halite.auth.cookies import CookieCodec
from halite.config import Settings
from halite.main import create_app


def _app(app_db, *, demo: bool):
    settings = Settings(database_url=app_db, cookie_secret="x" * 64,
                        cookie_secure=False, demo_mode=demo)
    return create_app(settings=settings, codec=CookieCodec(settings.cookie_secret))


@pytest.mark.asyncio
async def test_config_reports_demo_true(app_db):
    app = _app(app_db, demo=True)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
        r = await ac.get("/api/config")
    assert r.status_code == 200
    assert r.json() == {"demo": True}


@pytest.mark.asyncio
async def test_config_reports_demo_false_and_needs_no_auth(app_db):
    app = _app(app_db, demo=False)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
        r = await ac.get("/api/config")
    assert r.status_code == 200
    assert r.json() == {"demo": False}
