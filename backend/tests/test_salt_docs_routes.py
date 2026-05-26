# backend/tests/test_salt_docs_routes.py
from datetime import UTC, datetime

import pytest
from httpx import ASGITransport, AsyncClient

from halite.auth.cookies import CookieCodec
from halite.auth.models import User
from halite.auth.password import hash_password
from halite.auth.service import create_session
from halite.config import Settings
from halite.main import create_app
from halite.salt.client import SaltAPIClient
from halite.salt_docs import service as salt_docs_service


async def _logged_in_user(session) -> User:
    user = User(
        username_lower="alice",
        username="alice",
        password_hash=hash_password("pw"),
        is_active=True,
        created_at=datetime.now(tz=UTC),
    )
    session.add(user)
    await session.flush()
    await session.commit()
    await session.refresh(user)
    return user


def _attach_salt_client(app, fake_salt_api) -> SaltAPIClient:
    client = SaltAPIClient(
        base_url="http://salt.test",
        username="halite-service",
        password="pw",
        transport=fake_salt_api.transport,
    )
    app.state.salt_client = client
    return client


@pytest.fixture(autouse=True)
def _reset_cache():
    """Reset the module-level cache before AND after each test so cache
    state doesn't leak between cases."""
    salt_docs_service._reset_cache_for_tests()
    yield
    salt_docs_service._reset_cache_for_tests()


@pytest.mark.asyncio
async def test_list_functions_returns_sorted_names(app_db, session, fake_salt_api):
    settings = Settings(database_url=app_db, cookie_secret="x" * 64, cookie_secure=False)
    codec = CookieCodec(settings.cookie_secret)
    user = await _logged_in_user(session)
    sess = await create_session(session, user, user_agent="ua", ip="1.2.3.4", ttl_minutes=60)
    await session.commit()

    # list_execution_functions targets * with sys.list_functions and
    # unions across responding minions.
    def handler(payload):
        if payload.get("fun") == "sys.list_functions":
            return {"return": [{
                "web-01": ["test.ping", "cmd.run"],
                "web-02": ["cmd.run", "state.apply"],
            }]}
        return {"return": [{}]}

    fake_salt_api.run_handler = handler

    app = create_app(settings=settings, codec=codec)
    client = _attach_salt_client(app, fake_salt_api)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
            r = await ac.get(
                "/api/salt/functions",
                cookies={settings.cookie_name: codec.sign(sess.id)},
            )
    finally:
        await client.aclose()

    assert r.status_code == 200
    body = r.json()
    assert body["functions"] == ["cmd.run", "state.apply", "test.ping"]
    assert "cached_at" in body


@pytest.mark.asyncio
async def test_list_functions_serves_from_cache_on_second_call(app_db, session, fake_salt_api):
    settings = Settings(database_url=app_db, cookie_secret="x" * 64, cookie_secure=False)
    codec = CookieCodec(settings.cookie_secret)
    user = await _logged_in_user(session)
    sess = await create_session(session, user, user_agent="ua", ip="1.2.3.4", ttl_minutes=60)
    await session.commit()

    list_funcs_calls = 0
    def handler(payload):
        nonlocal list_funcs_calls
        if payload.get("fun") == "sys.list_functions":
            list_funcs_calls += 1
            return {"return": [{"web-01": ["test.ping"]}]}
        return {"return": [{}]}

    fake_salt_api.run_handler = handler

    app = create_app(settings=settings, codec=codec)
    client = _attach_salt_client(app, fake_salt_api)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
            r1 = await ac.get(
                "/api/salt/functions",
                cookies={settings.cookie_name: codec.sign(sess.id)},
            )
            r2 = await ac.get(
                "/api/salt/functions",
                cookies={settings.cookie_name: codec.sign(sess.id)},
            )
    finally:
        await client.aclose()

    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r1.json() == r2.json()
    # salt-api should only be called once thanks to the cache.
    assert list_funcs_calls == 1


@pytest.mark.asyncio
async def test_list_functions_503_when_salt_not_configured(app_db, session):
    settings = Settings(database_url=app_db, cookie_secret="x" * 64, cookie_secure=False)
    codec = CookieCodec(settings.cookie_secret)
    user = await _logged_in_user(session)
    sess = await create_session(session, user, user_agent="ua", ip="1.2.3.4", ttl_minutes=60)
    await session.commit()

    app = create_app(settings=settings, codec=codec)
    async with (
        AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac,
        app.router.lifespan_context(app),
    ):
        r = await ac.get(
            "/api/salt/functions",
            cookies={settings.cookie_name: codec.sign(sess.id)},
        )
    assert r.status_code == 503
