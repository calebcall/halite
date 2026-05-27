from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from halite.audit.models import AuditEntry
from halite.auth.cookies import CookieCodec
from halite.auth.models import User
from halite.auth.password import hash_password
from halite.auth.service import create_session
from halite.config import Settings
from halite.main import create_app
from halite.rbac.models import Permission, Role, UserRole
from halite.settings.models import AppSettings


class _StubRuntime:
    async def reload(self, db):
        pass

    async def boot(self, db):
        pass

    async def shutdown(self):
        pass


async def _settings_admin(session, username: str = "alice") -> User:
    """Create a user with the ``edit`` verb on ``settings:*``."""
    user = User(
        username_lower=username,
        username=username,
        password_hash=hash_password("pw"),
        is_active=True,
        created_at=datetime.now(tz=UTC),
    )
    session.add(user)
    await session.flush()
    role = Role(name=f"settings-admin-{username}", is_builtin=False, description="")
    session.add(role)
    await session.flush()
    session.add(Permission(role_id=role.id, verb="edit", resource_glob="settings:*"))
    session.add(UserRole(user_id=user.id, role_id=role.id))
    await session.commit()
    await session.refresh(user)
    return user


async def _plain_user(session, username: str = "bob") -> User:
    """Create a user with NO settings permissions."""
    user = User(
        username_lower=username,
        username=username,
        password_hash=hash_password("pw"),
        is_active=True,
        created_at=datetime.now(tz=UTC),
    )
    session.add(user)
    await session.flush()
    await session.commit()
    await session.refresh(user)
    return user


def _make_app(app_db: str, stub_runtime: bool = True):
    settings = Settings(database_url=app_db, cookie_secret="x" * 64, cookie_secure=False)
    codec = CookieCodec(settings.cookie_secret)
    app = create_app(settings=settings, codec=codec)
    if stub_runtime:
        app.state.runtime = _StubRuntime()
    return app, settings, codec


@pytest.mark.asyncio
async def test_get_settings_status_returns_unconfigured_on_empty_db(app_db, session):
    app, settings, codec = _make_app(app_db)
    user = await _settings_admin(session, "alice")
    sess = await create_session(session, user, user_agent="ua", ip="1.2.3.4", ttl_minutes=60)
    await session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
        r = await ac.get(
            "/api/admin/settings/status",
            cookies={settings.cookie_name: codec.sign(sess.id)},
        )

    assert r.status_code == 200
    body = r.json()
    assert body["configured"] is False
    assert set(body["missing"]) == {"salt.url", "salt.username", "salt.password"}


@pytest.mark.asyncio
async def test_get_settings_redacts_password(app_db, session):
    # Seed a password into the row; GET should show password_set=True, not the value.
    from halite.settings.crypto import encrypt_password

    row = (await session.execute(select(AppSettings))).scalar_one_or_none()
    if row is None:
        row = AppSettings(id=1, updated_at=datetime.now(tz=UTC))
        session.add(row)
        await session.flush()

    cookie_secret = "x" * 64
    row.salt_api_url = "http://salt:8000"
    row.salt_api_username = "halite"
    row.salt_api_password_encrypted = encrypt_password("s3cr3t", cookie_secret=cookie_secret)
    await session.commit()

    app, settings, codec = _make_app(app_db)
    user = await _settings_admin(session, "alice")
    sess = await create_session(session, user, user_agent="ua", ip="1.2.3.4", ttl_minutes=60)
    await session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
        r = await ac.get(
            "/api/admin/settings",
            cookies={settings.cookie_name: codec.sign(sess.id)},
        )

    assert r.status_code == 200
    body = r.json()
    # The password value must never appear in the response.
    assert "s3cr3t" not in str(body)
    assert body["salt"]["password_set"] is True
    assert body["salt"]["url"] == "http://salt:8000"


@pytest.mark.asyncio
async def test_put_salt_persists_and_audits(app_db, session):
    app, settings, codec = _make_app(app_db)
    user = await _settings_admin(session, "alice")
    sess = await create_session(session, user, user_agent="ua", ip="1.2.3.4", ttl_minutes=60)
    await session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
        r = await ac.put(
            "/api/admin/settings/salt",
            cookies={settings.cookie_name: codec.sign(sess.id)},
            json={"url": "http://salt:8000", "username": "admin", "password": "secret"},
        )

    assert r.status_code == 200
    body = r.json()
    assert body["salt"]["url"] == "http://salt:8000"
    assert body["salt"]["username"] == "admin"
    assert body["salt"]["password_set"] is True

    # Audit row must exist with redacted password.
    rows = (
        await session.execute(
            select(AuditEntry).where(AuditEntry.action == "settings.salt.update")
        )
    ).scalars().all()
    assert len(rows) == 1
    audit = rows[0]
    assert audit.decision == "allow"
    assert audit.result_code == 200
    assert audit.args_json is not None
    # The audit writer auto-redacts "password" keys.
    assert audit.args_json.get("password") != "secret"


@pytest.mark.asyncio
async def test_put_salt_extra_field_rejected(app_db, session):
    app, settings, codec = _make_app(app_db)
    user = await _settings_admin(session, "alice")
    sess = await create_session(session, user, user_agent="ua", ip="1.2.3.4", ttl_minutes=60)
    await session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
        r = await ac.put(
            "/api/admin/settings/salt",
            cookies={settings.cookie_name: codec.sign(sess.id)},
            json={"foo": "bar"},
        )

    assert r.status_code == 422


@pytest.mark.asyncio
async def test_put_pollers_validates_ranges(app_db, session):
    app, settings, codec = _make_app(app_db)
    user = await _settings_admin(session, "alice")
    sess = await create_session(session, user, user_agent="ua", ip="1.2.3.4", ttl_minutes=60)
    await session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
        r = await ac.put(
            "/api/admin/settings/pollers",
            cookies={settings.cookie_name: codec.sign(sess.id)},
            json={"minion_state_keys_interval_seconds": -1},
        )

    assert r.status_code == 422


@pytest.mark.asyncio
async def test_put_logging_changes_format(app_db, session):
    app, settings, codec = _make_app(app_db)
    user = await _settings_admin(session, "alice")
    sess = await create_session(session, user, user_agent="ua", ip="1.2.3.4", ttl_minutes=60)
    await session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
        r = await ac.put(
            "/api/admin/settings/logging",
            cookies={settings.cookie_name: codec.sign(sess.id)},
            json={"log_format": "text"},
        )

    assert r.status_code == 200
    assert r.json()["logging"]["log_format"] == "text"

    # Confirm the row was actually updated.
    row = (await session.execute(select(AppSettings))).scalar_one()
    assert row.log_format == "text"


@pytest.mark.asyncio
async def test_unauthorized_get_returns_403_without_settings_edit_verb(app_db, session):
    app, settings, codec = _make_app(app_db)
    user = await _plain_user(session, "bob")
    sess = await create_session(session, user, user_agent="ua", ip="1.2.3.4", ttl_minutes=60)
    await session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
        r = await ac.get(
            "/api/admin/settings",
            cookies={settings.cookie_name: codec.sign(sess.id)},
        )

    assert r.status_code == 403


@pytest.mark.asyncio
async def test_test_salt_returns_ok_for_valid_mock_client(app_db, session):
    app, settings, codec = _make_app(app_db)
    user = await _settings_admin(session, "alice")
    sess = await create_session(session, user, user_agent="ua", ip="1.2.3.4", ttl_minutes=60)
    await session.commit()

    with (
        patch(
            "halite.settings.routes.SaltAPIClient.login",
            new_callable=lambda: lambda self: AsyncMock(return_value=None)(),
        ),
        patch(
            "halite.settings.routes.SaltAPIClient.list_present_minion_ids",
            new_callable=lambda: lambda self: AsyncMock(
                return_value={"web-1", "web-2", "db-1"}
            )(),
        ),
        patch(
            "halite.settings.routes.SaltAPIClient.aclose",
            new_callable=lambda: lambda self: AsyncMock(return_value=None)(),
        ),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
            r = await ac.post(
                "/api/admin/settings/test-salt",
                cookies={settings.cookie_name: codec.sign(sess.id)},
                json={
                    "url": "http://salt:8000",
                    "username": "admin",
                    "password": "secret",
                    "verify": False,
                    "eauth": "pam",
                },
            )

    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["minion_count"] == 3


@pytest.mark.asyncio
async def test_test_salt_returns_failure_for_bad_creds(app_db, session):
    app, settings, codec = _make_app(app_db)
    user = await _settings_admin(session, "alice")
    sess = await create_session(session, user, user_agent="ua", ip="1.2.3.4", ttl_minutes=60)
    await session.commit()

    with patch(
        "halite.settings.routes.SaltAPIClient.login",
        new_callable=lambda: lambda self: _raise_on_call(RuntimeError("401 Unauthorized"))(),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
            r = await ac.post(
                "/api/admin/settings/test-salt",
                cookies={settings.cookie_name: codec.sign(sess.id)},
                json={
                    "url": "http://salt:8000",
                    "username": "admin",
                    "password": "wrong",
                    "verify": False,
                    "eauth": "pam",
                },
            )

    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is False
    assert body["detail"].startswith("auth failed")


def _raise_on_call(exc: Exception):
    """Return a no-arg async callable that raises exc."""
    async def _raiser():
        raise exc
    return _raiser
