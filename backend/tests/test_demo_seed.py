import pytest

from halite.auth.service import _find_user_by_username
from halite.auth.password import verify_password
from halite.config import Settings
from halite.demo import seed_demo
from halite.rbac.engine import check
from halite.rbac.seed import seed_builtin_roles
from halite.bootstrap import bootstrap_admin
from halite.auth.permissions_cache import load_permissions_for
from halite.settings.service import app_settings_row


def _settings():
    return Settings(database_url="sqlite+aiosqlite://", cookie_secret="x" * 64,
                    demo_mode=True, demo_admin_password="s3cret-admin",
                    demo_salt_url="http://mock-salt-api:8000",
                    demo_salt_username="halite-demo", demo_salt_password="demo")


@pytest.mark.asyncio
async def test_seed_creates_demo_user_with_readonly_role(session):
    await seed_builtin_roles(session); await session.commit()
    await bootstrap_admin(session); await session.commit()
    await seed_demo(session, _settings()); await session.commit()

    demo = await _find_user_by_username(session, "demo")
    assert demo is not None and demo.is_active and not demo.must_change_pw
    demo.permissions_cache = await load_permissions_for(session, demo)
    assert check(demo, "view", "minion:web01")
    assert check(demo, "execute", "salt:test.ping")
    assert check(demo, "accept", "key:web01")
    assert not check(demo, "manage_user", "user:bob")
    assert not check(demo, "manage_role", "role:ops")
    assert not check(demo, "edit", "settings:salt")


@pytest.mark.asyncio
async def test_seed_sets_admin_password_for_operator_login(session):
    await seed_builtin_roles(session); await session.commit()
    await bootstrap_admin(session); await session.commit()
    await seed_demo(session, _settings()); await session.commit()

    admin = await _find_user_by_username(session, "admin")
    assert admin is not None and not admin.must_change_pw
    assert verify_password(admin.password_hash, "s3cret-admin")
    admin.permissions_cache = await load_permissions_for(session, admin)
    assert check(admin, "edit", "settings:salt")


@pytest.mark.asyncio
async def test_seed_configures_salt_and_enables_features(session):
    await seed_builtin_roles(session); await session.commit()
    await bootstrap_admin(session); await session.commit()
    await seed_demo(session, _settings()); await session.commit()

    row = await app_settings_row(session)
    assert row.salt_api_url == "http://mock-salt-api:8000"
    assert row.salt_api_username == "halite-demo"
    assert row.salt_api_password_encrypted
    assert row.salt_api_verify is False
    assert row.event_stream_enabled is True
    assert row.jobs_poll_interval_seconds > 0
    assert row.fleet_poll_interval_seconds > 0


@pytest.mark.asyncio
async def test_seed_is_idempotent(session):
    await seed_builtin_roles(session); await session.commit()
    await bootstrap_admin(session); await session.commit()
    await seed_demo(session, _settings()); await session.commit()
    await seed_demo(session, _settings()); await session.commit()
    demo = await _find_user_by_username(session, "demo")
    assert demo is not None
