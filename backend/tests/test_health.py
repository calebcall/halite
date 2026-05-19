import pytest
from httpx import ASGITransport, AsyncClient

from halite.auth.cookies import CookieCodec
from halite.config import Settings
from halite.main import create_app


@pytest.mark.asyncio
async def test_healthz_returns_ok():
    settings = Settings(database_url="sqlite+aiosqlite:///:memory:", cookie_secret="x" * 64)
    app = create_app(settings=settings, codec=CookieCodec(settings.cookie_secret))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_readyz_returns_ok_when_db_reachable(app_db):
    settings = Settings(database_url=app_db, cookie_secret="x" * 64, cookie_secure=False)
    app = create_app(settings=settings, codec=CookieCodec(settings.cookie_secret))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        r = await ac.get("/readyz")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ready"
    assert body["checks"]["db"] == "ok"


@pytest.mark.asyncio
async def test_serves_spa_index_at_root(tmp_path, monkeypatch):
    # Fake a built frontend at a temp dir
    static_dir = tmp_path / "static"
    static_dir.mkdir()
    (static_dir / "index.html").write_text("<!doctype html><title>Halite</title>")
    (static_dir / "assets").mkdir()

    monkeypatch.setenv("HALITE_STATIC_DIR", str(static_dir))

    from halite.auth.cookies import CookieCodec
    from halite.config import Settings
    settings = Settings(database_url="sqlite+aiosqlite:///:memory:", cookie_secret="x" * 64)
    app = create_app(settings=settings, codec=CookieCodec(settings.cookie_secret))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        r = await ac.get("/")
    assert r.status_code == 200
    assert "Halite" in r.text
