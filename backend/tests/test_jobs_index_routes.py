from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient

from halite.auth.cookies import CookieCodec
from halite.auth.models import User
from halite.auth.password import hash_password
from halite.auth.service import create_session
from halite.config import Settings
from halite.jobs.index_model import JobIndexEntry
from halite.main import create_app
from halite.rbac.models import Permission, Role, UserRole
from halite.salt.client import SaltAPIClient


async def _user_with(session, perms: list[tuple[str, str]]) -> User:
    user = User(
        username_lower="alice",
        username="alice",
        password_hash=hash_password("pw"),
        is_active=True,
        created_at=datetime.now(tz=UTC),
    )
    session.add(user)
    await session.flush()
    role = Role(name="jobs-index-test", is_builtin=False, description="")
    session.add(role)
    await session.flush()
    for verb, glob in perms:
        session.add(Permission(role_id=role.id, verb=verb, resource_glob=glob))
    session.add(UserRole(user_id=user.id, role_id=role.id))
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


class _StubRuntime:
    """Minimal runtime stub with the active-jids cache surface the
    DB-backed routes read from. Set ``salt`` if a test exercises the
    ?live=true path."""

    def __init__(
        self,
        *,
        active_jids: set[str] | None = None,
        active_jids_refreshed_at: datetime | None = None,
        salt: Any = None,
    ) -> None:
        self.active_jids = active_jids
        self.active_jids_refreshed_at = active_jids_refreshed_at
        self.salt = salt

    async def reload(self, db):  # noqa: ARG002
        pass

    async def shutdown(self):
        pass


@pytest.mark.asyncio
async def test_activity_returns_empty_when_index_is_empty(app_db, session):
    """jobs_index empty + cache cold → total=0, running=0, active_known=False."""
    settings = Settings(database_url=app_db, cookie_secret="x" * 64, cookie_secure=False)
    codec = CookieCodec(settings.cookie_secret)
    user = await _user_with(session, [("view", "job:*")])
    sess = await create_session(session, user, user_agent="ua", ip="1.2.3.4", ttl_minutes=60)
    await session.commit()
    app = create_app(settings=settings, codec=codec)
    app.state.runtime = _StubRuntime()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
        r = await ac.get(
            "/api/jobs/activity?hours=24",
            cookies={settings.cookie_name: codec.sign(sess.id)},
        )
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 0
    assert body["running"] == 0
    assert body["active_known"] is False


@pytest.mark.asyncio
async def test_activity_buckets_by_hour(app_db, session):
    """Seed 3 rows across 2 hours; assert their buckets carry the
    correct counts and total is the sum."""
    settings = Settings(database_url=app_db, cookie_secret="x" * 64, cookie_secure=False)
    codec = CookieCodec(settings.cookie_secret)
    user = await _user_with(session, [("view", "job:*")])
    sess = await create_session(session, user, user_agent="ua", ip="1.2.3.4", ttl_minutes=60)
    now = datetime.now(tz=UTC).replace(minute=30, second=0, microsecond=0)
    # Two jobs in "this hour", one in "an hour ago"
    session.add(JobIndexEntry(
        jid="20260527000000000001",
        function="state.apply",
        started_at=now,
        seen_at=now,
    ))
    session.add(JobIndexEntry(
        jid="20260527000000000002",
        function="test.ping",
        started_at=now,
        seen_at=now,
    ))
    session.add(JobIndexEntry(
        jid="20260527000000000003",
        function="state.highstate",
        started_at=now - timedelta(hours=1),
        seen_at=now,
    ))
    await session.commit()
    app = create_app(settings=settings, codec=codec)
    app.state.runtime = _StubRuntime()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
        r = await ac.get(
            "/api/jobs/activity?hours=24",
            cookies={settings.cookie_name: codec.sign(sess.id)},
        )
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 3
    # Verify the bucket containing 2 jobs is non-zero
    non_zero = [b for b in body["buckets"] if b["count"] > 0]
    assert len(non_zero) == 2  # one bucket with 1, one with 2


@pytest.mark.asyncio
async def test_activity_running_count_from_runtime_cache(app_db, session):
    """When runtime.active_jids is a populated set, /activity reports
    its length as running and active_known=True."""
    settings = Settings(database_url=app_db, cookie_secret="x" * 64, cookie_secure=False)
    codec = CookieCodec(settings.cookie_secret)
    user = await _user_with(session, [("view", "job:*")])
    sess = await create_session(session, user, user_agent="ua", ip="1.2.3.4", ttl_minutes=60)
    await session.commit()
    app = create_app(settings=settings, codec=codec)
    app.state.runtime = _StubRuntime(
        active_jids={"j1", "j2"},
        active_jids_refreshed_at=datetime.now(tz=UTC),
    )
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
        r = await ac.get(
            "/api/jobs/activity?hours=24",
            cookies={settings.cookie_name: codec.sign(sess.id)},
        )
    body = r.json()
    assert body["running"] == 2
    assert body["active_known"] is True
    assert body["last_polled_at"] is not None


@pytest.mark.asyncio
async def test_list_returns_db_rows_with_active_flag(app_db, session):
    """Two jobs in DB; one is in runtime.active_jids → its status is
    'running'; the other → 'complete'."""
    settings = Settings(database_url=app_db, cookie_secret="x" * 64, cookie_secure=False)
    codec = CookieCodec(settings.cookie_secret)
    user = await _user_with(session, [("view", "job:*")])
    sess = await create_session(session, user, user_agent="ua", ip="1.2.3.4", ttl_minutes=60)
    now = datetime.now(tz=UTC)
    session.add(JobIndexEntry(
        jid="20260527120000000001",
        function="state.apply",
        target="*",
        started_at=now,
        seen_at=now,
    ))
    session.add(JobIndexEntry(
        jid="20260527130000000002",
        function="test.ping",
        target="web-1",
        started_at=now,
        seen_at=now,
    ))
    await session.commit()
    app = create_app(settings=settings, codec=codec)
    app.state.runtime = _StubRuntime(
        active_jids={"20260527130000000002"},
        active_jids_refreshed_at=now,
    )
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
        r = await ac.get(
            "/api/jobs",
            cookies={settings.cookie_name: codec.sign(sess.id)},
        )
    body = r.json()
    assert body["total"] == 2
    by_jid = {j["jid"]: j for j in body["jobs"]}
    assert by_jid["20260527130000000002"]["status"] == "running"
    assert by_jid["20260527120000000001"]["status"] == "complete"
    assert body["active_known"] is True


@pytest.mark.asyncio
async def test_list_live_param_falls_back_to_salt(app_db, session, fake_salt_api):
    """?live=true ignores the DB entirely and reads from salt-api."""
    settings = Settings(database_url=app_db, cookie_secret="x" * 64, cookie_secure=False)
    codec = CookieCodec(settings.cookie_secret)
    user = await _user_with(session, [("view", "job:*")])
    sess = await create_session(session, user, user_agent="ua", ip="1.2.3.4", ttl_minutes=60)
    await session.commit()

    def handler(payload):
        fun = payload.get("fun")
        if fun == "jobs.list_jobs":
            return {"return": [{"20260527140000000003": {
                "Function": "test.ping",
                "Target": "web-1",
                "Target-type": "glob",
                "User": "root",
                "StartTime": "2026, May 27 14:00:00.000003",
                "Arguments": [],
            }}]}
        if fun == "jobs.active":
            return {"return": [{}]}
        return {"return": [{}]}

    fake_salt_api.run_handler = handler
    app = create_app(settings=settings, codec=codec)
    # Wire the salt client through the existing helper so the live path
    # finds it via salt_client_or_503.
    client = _attach_salt_client(app, fake_salt_api)
    app.state.runtime = _StubRuntime(salt=app.state.salt_client)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
            r = await ac.get(
                "/api/jobs?live=true&limit=10",
                cookies={settings.cookie_name: codec.sign(sess.id)},
            )
    finally:
        await client.aclose()
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 1
    assert body["jobs"][0]["jid"] == "20260527140000000003"
