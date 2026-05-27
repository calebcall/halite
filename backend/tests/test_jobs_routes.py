# backend/tests/test_jobs_routes.py
from datetime import UTC, datetime

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
    role = Role(name="jobs-test", is_builtin=False, description="")
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


def _jobs_handler(
    list_payload: dict | None = None,
    detail_payload: dict | None = None,
    active_payload: dict | None = None,
):
    def handler(payload):
        fun = payload.get("fun", "")
        if fun == "jobs.list_jobs":
            return {"return": [list_payload or {}]}
        if fun == "jobs.list_job":
            return {"return": [detail_payload or {}]}
        if fun == "jobs.active":
            return {"return": [active_payload or {}]}
        return {"return": [{"data": {"return": {}}}]}
    return handler


@pytest.mark.asyncio
async def test_jobs_list_live_returns_summaries(app_db, session, fake_salt_api):
    """?live=true path hits Salt and returns the live summary list."""
    settings = Settings(database_url=app_db, cookie_secret="x" * 64, cookie_secure=False)
    codec = CookieCodec(settings.cookie_secret)
    user = await _user_with(session, [("view", "job:*")])
    sess = await create_session(session, user, user_agent="ua", ip="1.2.3.4", ttl_minutes=60)
    await session.commit()

    fake_salt_api.run_handler = _jobs_handler(
        list_payload={
            "20251019120000123456": {
                "Function": "test.ping", "Target": "*", "Target-type": "glob",
                "User": "halite-service", "StartTime": "2025-10-19T12:00:00.123456",
            },
            "20251019110000000000": {
                "Function": "cmd.run", "Target": "web-01", "Target-type": "glob",
                "User": "halite-service", "StartTime": "2025-10-19T11:00:00.000000",
            },
        },
        active_payload={
            "20251019120000123456": {"Function": "test.ping"},
        },
    )

    app = create_app(settings=settings, codec=codec)
    client = _attach_salt_client(app, fake_salt_api)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
            r = await ac.get(
                "/api/jobs?live=true",
                cookies={settings.cookie_name: codec.sign(sess.id)},
            )
    finally:
        await client.aclose()

    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 2
    assert body["jobs"][0]["jid"] == "20251019120000123456"
    assert body["jobs"][0]["function"] == "test.ping"
    assert body["jobs"][1]["function"] == "cmd.run"
    by_jid = {j["jid"]: j for j in body["jobs"]}
    assert by_jid["20251019120000123456"]["status"] == "running"
    assert by_jid["20251019110000000000"]["status"] == "complete"


@pytest.mark.asyncio
async def test_jobs_list_live_defaults_to_complete_when_active_is_empty(app_db, session, fake_salt_api):
    """?live=true: job not in active set → status == 'complete'."""
    settings = Settings(database_url=app_db, cookie_secret="x" * 64, cookie_secure=False)
    codec = CookieCodec(settings.cookie_secret)
    user = await _user_with(session, [("view", "job:*")])
    sess = await create_session(session, user, user_agent="ua", ip="1.2.3.4", ttl_minutes=60)
    await session.commit()

    fake_salt_api.run_handler = _jobs_handler(
        list_payload={
            "20251019120000123456": {"Function": "test.ping", "Target": "*"},
        },
        active_payload={},  # no active jobs
    )

    app = create_app(settings=settings, codec=codec)
    client = _attach_salt_client(app, fake_salt_api)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
            r = await ac.get(
                "/api/jobs?live=true",
                cookies={settings.cookie_name: codec.sign(sess.id)},
            )
    finally:
        await client.aclose()

    assert r.status_code == 200
    body = r.json()
    assert body["jobs"][0]["status"] == "complete"


@pytest.mark.asyncio
async def test_jobs_list_403_without_perm(app_db, session, fake_salt_api):
    settings = Settings(database_url=app_db, cookie_secret="x" * 64, cookie_secure=False)
    codec = CookieCodec(settings.cookie_secret)
    user = await _user_with(session, [("view", "minion:*")])  # not job:*
    sess = await create_session(session, user, user_agent="ua", ip="1.2.3.4", ttl_minutes=60)
    await session.commit()

    fake_salt_api.run_handler = _jobs_handler()

    app = create_app(settings=settings, codec=codec)
    client = _attach_salt_client(app, fake_salt_api)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
            r = await ac.get("/api/jobs", cookies={settings.cookie_name: codec.sign(sess.id)})
    finally:
        await client.aclose()
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_job_detail_returns_per_minion_results(app_db, session, fake_salt_api):
    settings = Settings(database_url=app_db, cookie_secret="x" * 64, cookie_secure=False)
    codec = CookieCodec(settings.cookie_secret)
    user = await _user_with(session, [("view", "job:*")])
    sess = await create_session(session, user, user_agent="ua", ip="1.2.3.4", ttl_minutes=60)
    await session.commit()

    fake_salt_api.run_handler = _jobs_handler(detail_payload={
        "Function": "state.apply",
        "Arguments": ["mystate", {"__kwarg__": True, "pillar": {"foo": "bar"}}],
        "Target": "*",
        "Target-type": "glob",
        "User": "halite-service",
        "StartTime": "2025-10-19T12:00:00.123456",
        "Minions": ["web-01", "web-02"],
        "Result": {
            "web-01": {"return": True, "success": True, "retcode": 0},
            "web-02": {"return": "perm denied", "success": False, "retcode": 1},
        },
    })

    app = create_app(settings=settings, codec=codec)
    client = _attach_salt_client(app, fake_salt_api)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
            r = await ac.get(
                "/api/jobs/20251019120000123456",
                cookies={settings.cookie_name: codec.sign(sess.id)},
            )
    finally:
        await client.aclose()

    assert r.status_code == 200
    body = r.json()
    assert body["jid"] == "20251019120000123456"
    assert body["function"] == "state.apply"
    assert body["minions"] == ["web-01", "web-02"]
    results_by_minion = {r["minion"]: r for r in body["results"]}
    assert results_by_minion["web-01"]["success"] is True
    assert results_by_minion["web-01"]["return_value"] is True
    assert results_by_minion["web-02"]["success"] is False
    assert results_by_minion["web-02"]["retcode"] == 1
    assert body["arguments"] == ["mystate"]
    assert body["kwargs"] == {"pillar": {"foo": "bar"}}


@pytest.mark.asyncio
async def test_job_detail_404_unknown_jid(app_db, session, fake_salt_api):
    settings = Settings(database_url=app_db, cookie_secret="x" * 64, cookie_secure=False)
    codec = CookieCodec(settings.cookie_secret)
    user = await _user_with(session, [("view", "job:*")])
    sess = await create_session(session, user, user_agent="ua", ip="1.2.3.4", ttl_minutes=60)
    await session.commit()

    fake_salt_api.run_handler = _jobs_handler(detail_payload={})

    app = create_app(settings=settings, codec=codec)
    client = _attach_salt_client(app, fake_salt_api)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
            r = await ac.get(
                "/api/jobs/nonexistent",
                cookies={settings.cookie_name: codec.sign(sess.id)},
            )
    finally:
        await client.aclose()
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_jobs_list_live_503_when_salt_not_configured(app_db, session):
    """?live=true: 503 when no Salt client is configured (DB default returns 200)."""
    settings = Settings(database_url=app_db, cookie_secret="x" * 64, cookie_secure=False)
    codec = CookieCodec(settings.cookie_secret)
    user = await _user_with(session, [("view", "job:*")])
    sess = await create_session(session, user, user_agent="ua", ip="1.2.3.4", ttl_minutes=60)
    await session.commit()

    app = create_app(settings=settings, codec=codec)
    async with (
        AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac,
        app.router.lifespan_context(app),
    ):
        r = await ac.get(
            "/api/jobs?live=true",
            cookies={settings.cookie_name: codec.sign(sess.id)},
        )
    assert r.status_code == 503


@pytest.mark.asyncio
async def test_kill_job_202_and_audit(app_db, session, fake_salt_api):
    settings = Settings(database_url=app_db, cookie_secret="x" * 64, cookie_secure=False)
    codec = CookieCodec(settings.cookie_secret)
    user = await _user_with(session, [("kill", "job:*")])
    sess = await create_session(session, user, user_agent="ua", ip="1.2.3.4", ttl_minutes=60)
    await session.commit()

    def handler(payload):
        return {"return": [{"web-01": True}]}
    fake_salt_api.run_handler = handler

    app = create_app(settings=settings, codec=codec)
    client = _attach_salt_client(app, fake_salt_api)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
            r = await ac.post(
                "/api/jobs/20260123120000000000/kill",
                cookies={settings.cookie_name: codec.sign(sess.id)},
            )
    finally:
        await client.aclose()
    assert r.status_code == 202

    rows = (
        await session.execute(select(AuditEntry).where(AuditEntry.action == "job.kill"))
    ).scalars().all()
    assert len(rows) == 1
    assert rows[0].resource == "job:20260123120000000000"
    assert rows[0].decision == "allow"
    assert rows[0].salt_jid == "20260123120000000000"


@pytest.mark.asyncio
async def test_kill_job_403_without_kill_verb(app_db, session, fake_salt_api):
    settings = Settings(database_url=app_db, cookie_secret="x" * 64, cookie_secure=False)
    codec = CookieCodec(settings.cookie_secret)
    user = await _user_with(session, [("view", "job:*")])  # not kill
    sess = await create_session(session, user, user_agent="ua", ip="1.2.3.4", ttl_minutes=60)
    await session.commit()

    fake_salt_api.run_handler = lambda p: {"return": [{}]}

    app = create_app(settings=settings, codec=codec)
    client = _attach_salt_client(app, fake_salt_api)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
            r = await ac.post(
                "/api/jobs/20260123120000000000/kill",
                cookies={settings.cookie_name: codec.sign(sess.id)},
            )
    finally:
        await client.aclose()
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_kill_job_502_and_deny_audit(app_db, session, fake_salt_api):
    settings = Settings(database_url=app_db, cookie_secret="x" * 64, cookie_secure=False)
    codec = CookieCodec(settings.cookie_secret)
    user = await _user_with(session, [("kill", "job:*")])
    sess = await create_session(session, user, user_agent="ua", ip="1.2.3.4", ttl_minutes=60)
    await session.commit()

    # 400 from salt-api is a non-retryable SaltAPIError → wrap_salt_errors → 502.
    # (run_status=500 would retry 3x then raise SaltAPIUnavailable → 503, slow.)
    fake_salt_api.run_status = 400

    app = create_app(settings=settings, codec=codec)
    client = _attach_salt_client(app, fake_salt_api)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
            r = await ac.post(
                "/api/jobs/20260123120000000000/kill",
                cookies={settings.cookie_name: codec.sign(sess.id)},
            )
    finally:
        await client.aclose()
    # 4xx (non-401) from salt-api → SaltAPIError → wrap_salt_errors → 502
    assert r.status_code == 502
    rows = (
        await session.execute(select(AuditEntry).where(AuditEntry.action == "job.kill"))
    ).scalars().all()
    assert len(rows) == 1
    assert rows[0].decision == "deny"
    assert rows[0].salt_jid == "20260123120000000000"
    assert rows[0].result_code == 502


def test_split_args_and_kwargs_with_trailing_kwarg():
    from halite.jobs.service import _split_args_and_kwargs
    positional, kwargs = _split_args_and_kwargs([
        "a1",
        "a2",
        {"__kwarg__": True, "k1": "v1", "k2": ["nested"]},
    ])
    assert positional == ["a1", "a2"]
    assert kwargs == {"k1": "v1", "k2": ["nested"]}


def test_split_args_and_kwargs_with_no_kwarg():
    from halite.jobs.service import _split_args_and_kwargs
    positional, kwargs = _split_args_and_kwargs(["a1", "a2"])
    assert positional == ["a1", "a2"]
    assert kwargs == {}


def test_split_args_and_kwargs_with_empty_args():
    from halite.jobs.service import _split_args_and_kwargs
    positional, kwargs = _split_args_and_kwargs([])
    assert positional == []
    assert kwargs == {}


def test_split_args_and_kwargs_trailing_dict_without_marker():
    """A trailing dict that doesn't have __kwarg__: True is NOT kwargs."""
    from halite.jobs.service import _split_args_and_kwargs
    positional, kwargs = _split_args_and_kwargs(["a1", {"plain": "dict"}])
    assert positional == ["a1", {"plain": "dict"}]
    assert kwargs == {}
