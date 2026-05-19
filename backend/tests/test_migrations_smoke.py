from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect


def test_migrations_create_users_and_sessions(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    url = f"sqlite+aiosqlite:///{db_path}"
    monkeypatch.setenv("DATABASE_URL", url)
    monkeypatch.setenv("COOKIE_SECRET", "x" * 64)

    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", url)
    command.upgrade(cfg, "head")

    sync_url = f"sqlite:///{db_path}"
    engine = create_engine(sync_url)
    with engine.connect() as conn:
        names = inspect(conn).get_table_names()
    engine.dispose()
    assert "users" in names
    assert "sessions" in names
