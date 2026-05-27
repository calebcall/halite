from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from httpx import ASGITransport, AsyncClient

from halite.auth.cookies import CookieCodec
from halite.auth.models import User
from halite.auth.password import hash_password
from halite.auth.service import create_session
from halite.config import Settings
from halite.fleet.models import HighstateRun
from halite.main import create_app
from halite.salt.client import SaltAPIClient


async def _user(session, username: str) -> User:
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


async def _seed_run(
    session,
    *,
    minion_id: str,
    jid: str,
    pass_count: int = 10,
    fail_count: int = 0,
    change_count: int = 0,
    total_count: int = 10,
    blocked: bool = False,
    age_minutes: int = 5,
    raw_result: dict | None = None,
) -> HighstateRun:
    row = HighstateRun(
        id=uuid.uuid4(),
        minion_id=minion_id,
        jid=jid,
        fun="state.apply",
        completed_at=datetime.now(tz=UTC) - timedelta(minutes=age_minutes),
        pass_count=pass_count,
        fail_count=fail_count,
        change_count=change_count,
        total_count=total_count,
        duration_ms=1000,
        blocked=blocked,
        raw_result=raw_result or {},
    )
    session.add(row)
    return row


def _attach_salt_client(app, fake_salt_api) -> SaltAPIClient:
    client = SaltAPIClient(
        base_url="http://salt.test",
        username="halite-service",
        password="pw",
        transport=fake_salt_api.transport,
    )
    app.state.salt_client = client
    return client


def _manage_present_handler(connected: dict[str, str]):
    """Return a run_handler that responds to manage.present with the given map."""
    def handler(payload):
        fun = payload.get("fun", "")
        if fun == "manage.present":
            return {"return": [connected]}
        return {"return": [None]}
    return handler


class _StubScheduler:
    """Minimal scheduler stub that exposes a pre-set connectivity set."""

    def __init__(self, connected: set[str]) -> None:
        self._connected = connected

    @property
    def connected_minions(self) -> set[str]:
        return self._connected

    @property
    def connected_refreshed_at(self):
        return None


@pytest.mark.asyncio
async def test_health_returns_one_row_per_minion(app_db, session, fake_salt_api):
    settings = Settings(database_url=app_db, cookie_secret="x" * 64, cookie_secure=False)
    codec = CookieCodec(settings.cookie_secret)
    user = await _user(session, "alice")
    sess = await create_session(session, user, user_agent="ua", ip="1.2.3.4", ttl_minutes=60)

    # minion-a: older run then newer run — expect the newer jid
    await _seed_run(session, minion_id="minion-a", jid="jid-old", age_minutes=60)
    newer = await _seed_run(session, minion_id="minion-a", jid="jid-new", age_minutes=5)
    # minion-b: single failing run
    await _seed_run(session, minion_id="minion-b", jid="jid-b", age_minutes=10, fail_count=1)
    await session.commit()

    fake_salt_api.run_handler = _manage_present_handler({
        "minion-a": "10.0.0.1",
        "minion-b": "10.0.0.2",
    })

    app = create_app(settings=settings, codec=codec)
    client = _attach_salt_client(app, fake_salt_api)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
            r = await ac.get(
                "/api/fleet/health",
                cookies={settings.cookie_name: codec.sign(sess.id)},
            )
    finally:
        await client.aclose()

    assert r.status_code == 200
    body = r.json()
    assert body["total_minions"] == 2

    by_minion = {m["minion_id"]: m for m in body["minions"]}
    assert set(by_minion.keys()) == {"minion-a", "minion-b"}
    # minion-a must use the newer jid
    assert by_minion["minion-a"]["jid"] == newer.jid
    # minion-a is online with no failures → healthy
    assert by_minion["minion-a"]["status"] == "healthy"
    assert by_minion["minion-a"]["online"] is True
    # minion-b is online but has fail_count > 0 → unhealthy
    assert by_minion["minion-b"]["status"] == "unhealthy"
    assert by_minion["minion-b"]["online"] is True


@pytest.mark.asyncio
async def test_health_marks_stale_runs(app_db, session, fake_salt_api):
    settings = Settings(database_url=app_db, cookie_secret="x" * 64, cookie_secure=False)
    codec = CookieCodec(settings.cookie_secret)
    user = await _user(session, "alice")
    sess = await create_session(session, user, user_agent="ua", ip="1.2.3.4", ttl_minutes=60)

    # 5 days old — well past the 2-day stale threshold
    await _seed_run(session, minion_id="minion-x", jid="jid-stale", age_minutes=5 * 24 * 60)
    await session.commit()

    fake_salt_api.run_handler = _manage_present_handler({"minion-x": "10.0.0.1"})

    app = create_app(settings=settings, codec=codec)
    client = _attach_salt_client(app, fake_salt_api)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
            r = await ac.get(
                "/api/fleet/health",
                cookies={settings.cookie_name: codec.sign(sess.id)},
            )
    finally:
        await client.aclose()

    assert r.status_code == 200
    minions = r.json()["minions"]
    assert len(minions) == 1
    assert minions[0]["status"] == "stale"
    assert minions[0]["online"] is True


@pytest.mark.asyncio
async def test_health_marks_blocked(app_db, session, fake_salt_api):
    settings = Settings(database_url=app_db, cookie_secret="x" * 64, cookie_secure=False)
    codec = CookieCodec(settings.cookie_secret)
    user = await _user(session, "alice")
    sess = await create_session(session, user, user_agent="ua", ip="1.2.3.4", ttl_minutes=60)

    await _seed_run(session, minion_id="minion-y", jid="jid-blocked", blocked=True)
    await session.commit()

    fake_salt_api.run_handler = _manage_present_handler({"minion-y": "10.0.0.1"})

    app = create_app(settings=settings, codec=codec)
    client = _attach_salt_client(app, fake_salt_api)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
            r = await ac.get(
                "/api/fleet/health",
                cookies={settings.cookie_name: codec.sign(sess.id)},
            )
    finally:
        await client.aclose()

    assert r.status_code == 200
    minions = r.json()["minions"]
    assert len(minions) == 1
    assert minions[0]["status"] == "blocked"
    assert minions[0]["online"] is True


@pytest.mark.asyncio
async def test_health_marks_offline_as_unhealthy(app_db, session, fake_salt_api):
    """A minion with a passing run that goes offline must appear as unhealthy."""
    settings = Settings(database_url=app_db, cookie_secret="x" * 64, cookie_secure=False)
    codec = CookieCodec(settings.cookie_secret)
    user = await _user(session, "alice")
    sess = await create_session(session, user, user_agent="ua", ip="1.2.3.4", ttl_minutes=60)

    await _seed_run(session, minion_id="web-1", jid="jid-pass", pass_count=10, fail_count=0)
    await session.commit()

    # Scheduler reports NO connected minions — web-1 is offline.
    app = create_app(settings=settings, codec=codec)
    app.state.fleet_scheduler = _StubScheduler(set())
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
        r = await ac.get(
            "/api/fleet/health",
            cookies={settings.cookie_name: codec.sign(sess.id)},
        )

    assert r.status_code == 200
    body = r.json()
    assert body["total_minions"] == 1
    assert body["minions"][0]["minion_id"] == "web-1"
    assert body["minions"][0]["status"] == "unhealthy"
    assert body["minions"][0]["online"] is False


@pytest.mark.asyncio
async def test_health_includes_online_minion_without_runs(app_db, session, fake_salt_api):
    """A minion that's online but has no ingested runs appears as unknown."""
    settings = Settings(database_url=app_db, cookie_secret="x" * 64, cookie_secure=False)
    codec = CookieCodec(settings.cookie_secret)
    user = await _user(session, "alice")
    sess = await create_session(session, user, user_agent="ua", ip="1.2.3.4", ttl_minutes=60)
    # No runs seeded at all.
    await session.commit()

    # Scheduler reports web-1 as connected even though it has no runs.
    app = create_app(settings=settings, codec=codec)
    app.state.fleet_scheduler = _StubScheduler({"web-1"})
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
        r = await ac.get(
            "/api/fleet/health",
            cookies={settings.cookie_name: codec.sign(sess.id)},
        )

    assert r.status_code == 200
    body = r.json()
    assert body["total_minions"] == 1
    assert body["minions"][0]["minion_id"] == "web-1"
    assert body["minions"][0]["status"] == "unknown"
    assert body["minions"][0]["online"] is True


@pytest.mark.asyncio
async def test_compliance_returns_oldest_first(app_db, session):
    settings = Settings(database_url=app_db, cookie_secret="x" * 64, cookie_secure=False)
    codec = CookieCodec(settings.cookie_secret)
    user = await _user(session, "alice")
    sess = await create_session(session, user, user_agent="ua", ip="1.2.3.4", ttl_minutes=60)

    # Two distinct jids at different ages
    await _seed_run(session, minion_id="minion-a", jid="jid-recent", age_minutes=10)
    await _seed_run(session, minion_id="minion-a", jid="jid-older", age_minutes=120)
    await session.commit()

    app = create_app(settings=settings, codec=codec)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
        r = await ac.get(
            "/api/fleet/compliance",
            cookies={settings.cookie_name: codec.sign(sess.id)},
        )

    assert r.status_code == 200
    buckets = r.json()["buckets"]
    assert len(buckets) == 2
    # Oldest first: bucketed_at[0] < bucketed_at[1]
    assert buckets[0]["bucketed_at"] < buckets[1]["bucketed_at"]


@pytest.mark.asyncio
async def test_top_failures_counts_unique_minions(app_db, session):
    settings = Settings(database_url=app_db, cookie_secret="x" * 64, cookie_secure=False)
    codec = CookieCodec(settings.cookie_secret)
    user = await _user(session, "alice")
    sess = await create_session(session, user, user_agent="ua", ip="1.2.3.4", ttl_minutes=60)

    raw_fail = {
        "service_|-redis_run_|-redis_|-running": {
            "result": False,
            "comment": "boom",
            "changes": {},
            "duration": 10.0,
            "__run_num__": 1,
        }
    }
    raw_pass = {
        "service_|-redis_run_|-redis_|-running": {
            "result": True,
            "comment": "",
            "changes": {},
            "duration": 10.0,
            "__run_num__": 1,
        }
    }

    # Two minions fail the state, one passes — all on the same jid
    await _seed_run(
        session, minion_id="minion-1", jid="jid-001", fail_count=1, raw_result=raw_fail
    )
    await _seed_run(
        session, minion_id="minion-2", jid="jid-001", fail_count=1, raw_result=raw_fail
    )
    await _seed_run(
        session, minion_id="minion-3", jid="jid-001", fail_count=0, raw_result=raw_pass
    )
    await session.commit()

    app = create_app(settings=settings, codec=codec)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
        r = await ac.get(
            "/api/fleet/top-failures",
            cookies={settings.cookie_name: codec.sign(sess.id)},
        )

    assert r.status_code == 200
    failures = r.json()["failures"]
    # Exactly one unique state reported
    assert len(failures) == 1
    assert failures[0]["failure_count"] == 2
    # state_id is the second segment of the low-state key ("redis_run")
    assert failures[0]["state_id"] == "redis_run"
    # name is the third segment ("redis")
    assert failures[0]["name"] == "redis"


@pytest.mark.asyncio
async def test_run_detail_404_for_unknown(app_db, session):
    settings = Settings(database_url=app_db, cookie_secret="x" * 64, cookie_secure=False)
    codec = CookieCodec(settings.cookie_secret)
    user = await _user(session, "alice")
    sess = await create_session(session, user, user_agent="ua", ip="1.2.3.4", ttl_minutes=60)
    await session.commit()

    random_id = uuid.uuid4()
    app = create_app(settings=settings, codec=codec)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
        r = await ac.get(
            f"/api/fleet/runs/{random_id}",
            cookies={settings.cookie_name: codec.sign(sess.id)},
        )

    assert r.status_code == 404


@pytest.mark.asyncio
async def test_routes_require_auth(app_db, session):
    settings = Settings(database_url=app_db, cookie_secret="x" * 64, cookie_secure=False)
    codec = CookieCodec(settings.cookie_secret)

    app = create_app(settings=settings, codec=codec)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
        r = await ac.get("/api/fleet/health")

    assert r.status_code == 401
