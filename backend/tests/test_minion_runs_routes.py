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
from halite.rbac.models import Permission, Role, UserRole


async def _viewer(session) -> User:
    user = User(
        username_lower="alice",
        username="alice",
        password_hash=hash_password("pw"),
        is_active=True,
        created_at=datetime.now(tz=UTC),
    )
    session.add(user)
    await session.flush()
    role = Role(name="viewer-runs-test", is_builtin=False, description="")
    session.add(role)
    await session.flush()
    session.add(Permission(role_id=role.id, verb="view", resource_glob="minion:*"))
    session.add(UserRole(user_id=user.id, role_id=role.id))
    await session.commit()
    await session.refresh(user)
    return user


def _run(
    *,
    minion_id: str = "web-1",
    jid: str = "J0",
    completed_at: datetime,
    pass_count: int = 0,
    fail_count: int = 0,
    change_count: int = 0,
    total_count: int = 0,
    blocked: bool = False,
) -> HighstateRun:
    return HighstateRun(
        id=uuid.uuid4(),
        minion_id=minion_id,
        jid=jid,
        fun="state.apply",
        completed_at=completed_at,
        pass_count=pass_count,
        fail_count=fail_count,
        change_count=change_count,
        total_count=total_count,
        duration_ms=1000,
        blocked=blocked,
        raw_result={},
    )


@pytest.mark.asyncio
async def test_list_runs_empty_for_unknown_minion(app_db, session):
    settings = Settings(database_url=app_db, cookie_secret="x" * 64, cookie_secure=False)
    codec = CookieCodec(settings.cookie_secret)
    user = await _viewer(session)
    sess = await create_session(session, user, user_agent="ua", ip="1.2.3.4", ttl_minutes=60)
    await session.commit()

    app = create_app(settings=settings, codec=codec)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
        r = await ac.get(
            "/api/minions/unknown/runs",
            cookies={settings.cookie_name: codec.sign(sess.id)},
        )

    assert r.status_code == 200
    body = r.json()
    assert body["minion_id"] == "unknown"
    assert body["total"] == 0
    assert body["runs"] == []


@pytest.mark.asyncio
async def test_list_runs_returns_newest_first(app_db, session):
    settings = Settings(database_url=app_db, cookie_secret="x" * 64, cookie_secure=False)
    codec = CookieCodec(settings.cookie_secret)
    user = await _viewer(session)
    sess = await create_session(session, user, user_agent="ua", ip="1.2.3.4", ttl_minutes=60)
    now = datetime.now(tz=UTC)
    session.add(_run(jid="J-old", completed_at=now - timedelta(hours=2), pass_count=3, total_count=3))
    session.add(_run(jid="J-mid", completed_at=now - timedelta(hours=1), pass_count=3, total_count=3))
    session.add(_run(jid="J-new", completed_at=now, pass_count=3, total_count=3))
    await session.commit()

    app = create_app(settings=settings, codec=codec)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
        r = await ac.get(
            "/api/minions/web-1/runs",
            cookies={settings.cookie_name: codec.sign(sess.id)},
        )

    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 3
    jids = [row["jid"] for row in body["runs"]]
    assert jids == ["J-new", "J-mid", "J-old"]


@pytest.mark.asyncio
async def test_list_runs_status_derives_correctly(app_db, session):
    settings = Settings(database_url=app_db, cookie_secret="x" * 64, cookie_secure=False)
    codec = CookieCodec(settings.cookie_secret)
    user = await _viewer(session)
    sess = await create_session(session, user, user_agent="ua", ip="1.2.3.4", ttl_minutes=60)
    now = datetime.now(tz=UTC)
    session.add(_run(
        jid="J-pass",
        completed_at=now - timedelta(minutes=4),
        pass_count=5,
        total_count=5,
    ))
    session.add(_run(
        jid="J-change",
        completed_at=now - timedelta(minutes=3),
        pass_count=4,
        change_count=1,
        total_count=5,
    ))
    session.add(_run(
        jid="J-fail",
        completed_at=now - timedelta(minutes=2),
        pass_count=4,
        fail_count=1,
        total_count=5,
    ))
    session.add(_run(
        jid="J-block",
        completed_at=now - timedelta(minutes=1),
        blocked=True,
        total_count=0,
    ))
    await session.commit()

    app = create_app(settings=settings, codec=codec)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
        r = await ac.get(
            "/api/minions/web-1/runs",
            cookies={settings.cookie_name: codec.sign(sess.id)},
        )

    assert r.status_code == 200
    by_jid = {row["jid"]: row["status"] for row in r.json()["runs"]}
    assert by_jid == {
        "J-pass": "healthy",
        "J-change": "changed",
        "J-fail": "unhealthy",
        "J-block": "blocked",
    }


@pytest.mark.asyncio
async def test_list_compliance_returns_oldest_first(app_db, session):
    settings = Settings(database_url=app_db, cookie_secret="x" * 64, cookie_secure=False)
    codec = CookieCodec(settings.cookie_secret)
    user = await _viewer(session)
    sess = await create_session(session, user, user_agent="ua", ip="1.2.3.4", ttl_minutes=60)
    now = datetime.now(tz=UTC)
    session.add(_run(jid="J-old", completed_at=now - timedelta(hours=1), pass_count=3, total_count=3))
    session.add(_run(jid="J-new", completed_at=now, pass_count=3, total_count=3))
    await session.commit()

    app = create_app(settings=settings, codec=codec)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
        r = await ac.get(
            "/api/minions/web-1/compliance",
            cookies={settings.cookie_name: codec.sign(sess.id)},
        )

    assert r.status_code == 200
    body = r.json()
    assert body["minion_id"] == "web-1"
    jids = [b["jid"] for b in body["buckets"]]
    assert jids == ["J-old", "J-new"]
