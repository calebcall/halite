import pytest

from halite.config import Settings


def test_settings_reads_database_url(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///./test.db")
    monkeypatch.setenv("COOKIE_SECRET", "x" * 64)
    settings = Settings()
    assert settings.database_url == "sqlite+aiosqlite:///./test.db"


def test_settings_rejects_short_cookie_secret(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///./test.db")
    monkeypatch.setenv("COOKIE_SECRET", "too-short")
    with pytest.raises(ValueError, match="at least 32"):
        Settings()


def test_settings_defaults(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///./test.db")
    monkeypatch.setenv("COOKIE_SECRET", "x" * 64)
    s = Settings()
    assert s.session_ttl_minutes == 480
    assert s.listen_port == 8080
