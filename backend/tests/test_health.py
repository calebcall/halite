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


@pytest.mark.asyncio
async def test_serves_root_static_files_not_spa_index(tmp_path, monkeypatch):
    # Real files at the static root (apple-touch-icon, favicon) must be served
    # as themselves — not swallowed by the SPA fallback. iOS Safari needs the
    # actual PNG when bookmarking to the home screen; HTML masquerading as a
    # PNG causes it to render a generated letter icon instead.
    static_dir = tmp_path / "static"
    static_dir.mkdir()
    (static_dir / "index.html").write_text("<!doctype html><title>Halite</title>")
    (static_dir / "assets").mkdir()
    png_bytes = b"\x89PNG\r\n\x1a\nfake-touch-icon"
    (static_dir / "apple-touch-icon.png").write_bytes(png_bytes)

    monkeypatch.setenv("HALITE_STATIC_DIR", str(static_dir))

    from halite.auth.cookies import CookieCodec
    from halite.config import Settings
    settings = Settings(database_url="sqlite+aiosqlite:///:memory:", cookie_secret="x" * 64)
    app = create_app(settings=settings, codec=CookieCodec(settings.cookie_secret))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        icon = await ac.get("/apple-touch-icon.png")
        unknown = await ac.get("/inventory/some-client-route")
    assert icon.status_code == 200
    assert icon.content == png_bytes
    # Client-side route still falls through to index.html for SPA routing.
    assert unknown.status_code == 200
    assert "Halite" in unknown.text
