from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient

from halite.auth.cookies import CookieCodec
from halite.auth.models import User
from halite.auth.password import hash_password
from halite.auth.service import create_session
from halite.config import Settings
from halite.fleet.models import HighstateRun
from halite.jobs.index_model import JobIndexEntry
from halite.main import create_app
from halite.rbac.models import Permission, Role, UserRole


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
    role = Role(name="timeline-test", is_builtin=False, description="")
    session.add(role)
    await session.flush()
    for verb, glob in perms:
        session.add(Permission(role_id=role.id, verb=verb, resource_glob=glob))
    session.add(UserRole(user_id=user.id, role_id=role.id))
    await session.commit()
    await session.refresh(user)
    return user


class _StubRuntime:
    """Minimal runtime stub with the active-jids cache surface the
    DB-backed routes read from."""

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
async def test_timeline_empty_returns_no_groups(app_db, session):
    settings = Settings(database_url=app_db, cookie_secret="x" * 64, cookie_secure=False)
    codec = CookieCodec(settings.cookie_secret)
    user = await _user_with(session, [("view", "job:*")])
    sess = await create_session(session, user, user_agent="ua", ip="1.2.3.4", ttl_minutes=60)
    await session.commit()
    app = create_app(settings=settings, codec=codec)
    app.state.runtime = _StubRuntime()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
        r = await ac.get(
            "/api/jobs/timeline?window=24h",
            cookies={settings.cookie_name: codec.sign(sess.id)},
        )
    assert r.status_code == 200
    body = r.json()
    assert body["total_bars"] == 0
    assert body["groups"] == []
    assert body["active_known"] is False


@pytest.mark.asyncio
async def test_timeline_groups_by_function(app_db, session):
    """Seed 3 jobs across 2 functions; assert 2 groups returned with
    correct bar_counts."""
    settings = Settings(database_url=app_db, cookie_secret="x" * 64, cookie_secure=False)
    codec = CookieCodec(settings.cookie_secret)
    user = await _user_with(session, [("view", "job:*")])
    sess = await create_session(session, user, user_agent="ua", ip="1.2.3.4", ttl_minutes=60)
    now = datetime.now(tz=UTC)
    session.add(JobIndexEntry(
        jid="20260527000000000010",
        function="state.apply",
        started_at=now - timedelta(hours=1),
        seen_at=now,
    ))
    session.add(JobIndexEntry(
        jid="20260527000000000011",
        function="state.apply",
        started_at=now - timedelta(hours=2),
        seen_at=now,
    ))
    session.add(JobIndexEntry(
        jid="20260527000000000012",
        function="test.ping",
        started_at=now - timedelta(hours=3),
        seen_at=now,
    ))
    await session.commit()
    app = create_app(settings=settings, codec=codec)
    app.state.runtime = _StubRuntime()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
        r = await ac.get(
            "/api/jobs/timeline?window=24h&group_by=function",
            cookies={settings.cookie_name: codec.sign(sess.id)},
        )
    assert r.status_code == 200
    body = r.json()
    assert body["total_bars"] == 3
    assert len(body["groups"]) == 2
    by_key = {g["key"]: g for g in body["groups"]}
    assert by_key["state.apply"]["bar_count"] == 2
    assert by_key["test.ping"]["bar_count"] == 1


@pytest.mark.asyncio
async def test_timeline_state_job_status_from_highstate_runs(app_db, session):
    """Seed a state.apply JobIndexEntry + 2 HighstateRun rows (one with
    fail_count=2, one with fail_count=0); assert bar.status == 'failed'
    and failed_minion_count == 1."""
    settings = Settings(database_url=app_db, cookie_secret="x" * 64, cookie_secure=False)
    codec = CookieCodec(settings.cookie_secret)
    user = await _user_with(session, [("view", "job:*")])
    sess = await create_session(session, user, user_agent="ua", ip="1.2.3.4", ttl_minutes=60)
    now = datetime.now(tz=UTC)
    jid = "20260527000000000020"
    session.add(JobIndexEntry(
        jid=jid,
        function="state.apply",
        started_at=now - timedelta(hours=1),
        seen_at=now,
    ))
    # Minion with failures
    session.add(HighstateRun(
        id=uuid.uuid4(),
        minion_id="minion-a",
        jid=jid,
        fun="state.apply",
        completed_at=now - timedelta(minutes=50),
        pass_count=8,
        fail_count=2,
        change_count=0,
        total_count=10,
        duration_ms=1200,
        blocked=False,
        raw_result={},
    ))
    # Minion without failures
    session.add(HighstateRun(
        id=uuid.uuid4(),
        minion_id="minion-b",
        jid=jid,
        fun="state.apply",
        completed_at=now - timedelta(minutes=45),
        pass_count=10,
        fail_count=0,
        change_count=0,
        total_count=10,
        duration_ms=900,
        blocked=False,
        raw_result={},
    ))
    await session.commit()
    app = create_app(settings=settings, codec=codec)
    app.state.runtime = _StubRuntime()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
        r = await ac.get(
            "/api/jobs/timeline?window=24h",
            cookies={settings.cookie_name: codec.sign(sess.id)},
        )
    assert r.status_code == 200
    body = r.json()
    assert body["total_bars"] == 1
    bar = body["groups"][0]["bars"][0]
    assert bar["status"] == "failed"
    assert bar["failed_minion_count"] == 1


@pytest.mark.asyncio
async def test_timeline_running_bar_from_active_jids(app_db, session):
    """Seed one job; stub runtime with active_jids={that jid}; assert
    bar.status == 'running' and completed_at is None."""
    settings = Settings(database_url=app_db, cookie_secret="x" * 64, cookie_secure=False)
    codec = CookieCodec(settings.cookie_secret)
    user = await _user_with(session, [("view", "job:*")])
    sess = await create_session(session, user, user_agent="ua", ip="1.2.3.4", ttl_minutes=60)
    now = datetime.now(tz=UTC)
    jid = "20260527000000000030"
    session.add(JobIndexEntry(
        jid=jid,
        function="state.apply",
        started_at=now - timedelta(minutes=5),
        seen_at=now,
    ))
    await session.commit()
    app = create_app(settings=settings, codec=codec)
    app.state.runtime = _StubRuntime(
        active_jids={jid},
        active_jids_refreshed_at=now,
    )
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
        r = await ac.get(
            "/api/jobs/timeline?window=24h",
            cookies={settings.cookie_name: codec.sign(sess.id)},
        )
    assert r.status_code == 200
    body = r.json()
    assert body["total_bars"] == 1
    bar = body["groups"][0]["bars"][0]
    assert bar["status"] == "running"
    assert bar["completed_at"] is None


@pytest.mark.asyncio
async def test_timeline_hides_system_jobs_by_default(app_db, session):
    """Seed runner.foo, wheel.bar, manage.baz, test.ping;
    GET with no include_system → only test.ping group returned;
    GET with ?include_system=true → all 4 groups returned."""
    settings = Settings(database_url=app_db, cookie_secret="x" * 64, cookie_secure=False)
    codec = CookieCodec(settings.cookie_secret)
    user = await _user_with(session, [("view", "job:*")])
    sess = await create_session(session, user, user_agent="ua", ip="1.2.3.4", ttl_minutes=60)
    now = datetime.now(tz=UTC)
    for idx, func in enumerate(["runner.foo", "wheel.bar", "manage.baz", "test.ping"]):
        jid = f"2026052700000000004{idx}"
        session.add(JobIndexEntry(
            jid=jid,
            function=func,
            started_at=now - timedelta(hours=idx + 1),
            seen_at=now,
        ))
    await session.commit()
    app = create_app(settings=settings, codec=codec)
    app.state.runtime = _StubRuntime()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
        # Default — system jobs hidden
        r_default = await ac.get(
            "/api/jobs/timeline?window=24h",
            cookies={settings.cookie_name: codec.sign(sess.id)},
        )
        # Explicit include_system=true
        r_all = await ac.get(
            "/api/jobs/timeline?window=24h&include_system=true",
            cookies={settings.cookie_name: codec.sign(sess.id)},
        )
    assert r_default.status_code == 200
    default_body = r_default.json()
    assert default_body["total_bars"] == 1
    assert default_body["groups"][0]["key"] == "test.ping"

    assert r_all.status_code == 200
    all_body = r_all.json()
    assert all_body["total_bars"] == 4
    all_keys = {g["key"] for g in all_body["groups"]}
    assert all_keys == {"runner.foo", "wheel.bar", "manage.baz", "test.ping"}


@pytest.mark.asyncio
async def test_timeline_filters_by_function_text(app_db, session):
    """Seed state.apply + test.ping; GET ?function_filter=state →
    only state.apply group returned."""
    settings = Settings(database_url=app_db, cookie_secret="x" * 64, cookie_secure=False)
    codec = CookieCodec(settings.cookie_secret)
    user = await _user_with(session, [("view", "job:*")])
    sess = await create_session(session, user, user_agent="ua", ip="1.2.3.4", ttl_minutes=60)
    now = datetime.now(tz=UTC)
    session.add(JobIndexEntry(
        jid="20260527000000000050",
        function="state.apply",
        started_at=now - timedelta(hours=1),
        seen_at=now,
    ))
    session.add(JobIndexEntry(
        jid="20260527000000000051",
        function="test.ping",
        started_at=now - timedelta(hours=2),
        seen_at=now,
    ))
    await session.commit()
    app = create_app(settings=settings, codec=codec)
    app.state.runtime = _StubRuntime()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
        r = await ac.get(
            "/api/jobs/timeline?window=24h&function_filter=state",
            cookies={settings.cookie_name: codec.sign(sess.id)},
        )
    assert r.status_code == 200
    body = r.json()
    assert body["total_bars"] == 1
    assert len(body["groups"]) == 1
    assert body["groups"][0]["key"] == "state.apply"
