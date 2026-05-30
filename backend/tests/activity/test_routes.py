from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from halite.activity.models import ActivityEvent
from halite.auth.cookies import CookieCodec
from halite.auth.models import User
from halite.auth.password import hash_password
from halite.auth.service import create_session
from halite.config import Settings
from halite.main import create_app
from halite.rbac.models import Permission, Role, UserRole


# The activity-package conftest shadows the root `session` fixture with an
# in-memory engine that is NOT the app's process-global engine. The route under
# test reads through `SessionDep` (the global engine wired by `app_db`), so we
# need a session bound to the SAME migrated DB the app uses. This fixture mirrors
# the root conftest `session` so seeded rows are visible to the running app.
@pytest_asyncio.fixture()
async def app_session(app_db):
    engine = create_async_engine(app_db)
    sm = async_sessionmaker(engine, expire_on_commit=False)
    async with sm() as s:
        yield s
    await engine.dispose()


async def _user_with(session: AsyncSession, perms: list[tuple[str, str]]) -> User:
    user = User(
        username_lower="alice",
        username="alice",
        password_hash=hash_password("pw"),
        is_active=True,
        created_at=datetime.now(tz=UTC),
    )
    session.add(user)
    await session.flush()
    role = Role(name="activity-routes-test", is_builtin=False, description="")
    session.add(role)
    await session.flush()
    for verb, glob in perms:
        session.add(Permission(role_id=role.id, verb=verb, resource_glob=glob))
    session.add(UserRole(user_id=user.id, role_id=role.id))
    await session.commit()
    await session.refresh(user)
    return user


async def _seed_events(session: AsyncSession) -> None:
    now = datetime.now(tz=UTC)
    rows = [
        ActivityEvent(
            ts=now,
            category="job",
            event_type="job_return",
            minion_id="web-1",
            jid="20260527000000000001",
            fun="state.apply",
            success=True,
            summary="job ran on web-1",
        ),
        ActivityEvent(
            ts=now,
            category="key",
            event_type="key_accept",
            minion_id="db-1",
            jid=None,
            fun=None,
            success=None,
            summary="key accepted for db-1",
        ),
        ActivityEvent(
            ts=now,
            category="minion",
            event_type="minion_start",
            minion_id="cache-1",
            jid=None,
            fun=None,
            success=None,
            summary="cache-1 came online",
        ),
    ]
    for r in rows:
        session.add(r)
    await session.commit()


async def _seed_job_rets(session: AsyncSession) -> None:
    """Four job.ret rows: a routine success (no change), a failure, a success
    that made changes, and a success with changed=NULL (pre-migration / non-state
    job return)."""
    now = datetime.now(tz=UTC)
    rows = [
        ActivityEvent(
            ts=now,
            category="job",
            event_type="job.ret",
            minion_id="web-1",
            jid="20260527000000000001",
            fun="state.highstate",
            success=True,
            changed=False,
            summary="web-1 returned state.highstate ✓",
        ),
        ActivityEvent(
            ts=now,
            category="job",
            event_type="job.ret",
            minion_id="web-2",
            jid="20260527000000000002",
            fun="state.highstate",
            success=False,
            changed=False,
            summary="web-2 returned state.highstate ✗",
        ),
        ActivityEvent(
            ts=now,
            category="job",
            event_type="job.ret",
            minion_id="web-3",
            jid="20260527000000000003",
            fun="state.highstate",
            success=True,
            changed=True,
            summary="web-3 returned state.highstate ✓",
        ),
        ActivityEvent(
            ts=now,
            category="job",
            event_type="job.ret",
            minion_id="web-4",
            jid="20260527000000000004",
            fun="test.ping",
            success=True,
            changed=None,
            summary="web-4 returned test.ping ✓",
        ),
    ]
    for r in rows:
        session.add(r)
    await session.commit()


@pytest.mark.asyncio
async def test_user_with_only_view_job_sees_only_job_events(app_db, app_session):
    """A user holding ONLY `view job:*` must see job events and have key/minion
    events filtered out by the in-handler permission scoping."""
    settings = Settings(database_url=app_db, cookie_secret="x" * 64, cookie_secure=False)
    codec = CookieCodec(settings.cookie_secret)
    user = await _user_with(app_session, [("view", "job:*")])
    sess = await create_session(
        app_session, user, user_agent="ua", ip="1.2.3.4", ttl_minutes=60
    )
    await app_session.commit()
    await _seed_events(app_session)

    app = create_app(settings=settings, codec=codec)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
        r = await ac.get(
            "/api/activity",
            cookies={settings.cookie_name: codec.sign(sess.id)},
        )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["total"] == 1
    assert {e["category"] for e in body["events"]} == {"job"}


@pytest.mark.asyncio
async def test_admin_filter_by_category_key(app_db, app_session):
    """A user with all perms filtering `?category=key` sees only key events."""
    settings = Settings(database_url=app_db, cookie_secret="x" * 64, cookie_secure=False)
    codec = CookieCodec(settings.cookie_secret)
    user = await _user_with(app_session, [("*", "*")])
    sess = await create_session(
        app_session, user, user_agent="ua", ip="1.2.3.4", ttl_minutes=60
    )
    await app_session.commit()
    await _seed_events(app_session)

    app = create_app(settings=settings, codec=codec)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
        r = await ac.get(
            "/api/activity?category=key",
            cookies={settings.cookie_name: codec.sign(sess.id)},
        )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["total"] == 1
    assert {e["category"] for e in body["events"]} == {"key"}


@pytest.mark.asyncio
async def test_admin_no_filter_sees_all_categories(app_db, app_session):
    """A user with all perms and no category filter sees every category."""
    settings = Settings(database_url=app_db, cookie_secret="x" * 64, cookie_secure=False)
    codec = CookieCodec(settings.cookie_secret)
    user = await _user_with(app_session, [("*", "*")])
    sess = await create_session(
        app_session, user, user_agent="ua", ip="1.2.3.4", ttl_minutes=60
    )
    await app_session.commit()
    await _seed_events(app_session)

    app = create_app(settings=settings, codec=codec)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
        r = await ac.get(
            "/api/activity",
            cookies={settings.cookie_name: codec.sign(sess.id)},
        )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["total"] == 3
    assert {e["category"] for e in body["events"]} == {"job", "key", "minion"}


@pytest.mark.asyncio
async def test_hide_routine_excludes_success_no_change(app_db, app_session):
    """hide_routine=true drops routine successes and keeps the failed / changed ones.

    Specifically verifies three exclusion cases:
    - changed=False, success=True  (web-1): excluded (routine no-change success)
    - changed=NULL,  success=True  (web-4): excluded (pre-migration / non-state
      job return — SQL uses ``changed IS NOT TRUE`` which matches both False and NULL)

    And two inclusion cases:
    - success=False (web-2): kept regardless of changed value
    - changed=True  (web-3): kept because the job made changes
    """
    settings = Settings(database_url=app_db, cookie_secret="x" * 64, cookie_secure=False)
    codec = CookieCodec(settings.cookie_secret)
    user = await _user_with(app_session, [("*", "*")])
    sess = await create_session(
        app_session, user, user_agent="ua", ip="1.2.3.4", ttl_minutes=60
    )
    await app_session.commit()
    await _seed_job_rets(app_session)

    app = create_app(settings=settings, codec=codec)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
        r = await ac.get(
            "/api/activity?hide_routine=true",
            cookies={settings.cookie_name: codec.sign(sess.id)},
        )
    assert r.status_code == 200, r.text
    body = r.json()
    minions = {e["minion_id"] for e in body["events"]}
    # web-1 (changed=False success) and web-4 (changed=NULL success) are hidden
    assert "web-1" not in minions, "changed=False success should be excluded"
    assert "web-4" not in minions, "changed=NULL success should be excluded"
    # web-2 (failed) and web-3 (changed=True) must be present
    assert minions == {"web-2", "web-3"}
    assert body["total"] == 2


@pytest.mark.asyncio
async def test_hide_routine_false_shows_all(app_db, app_session):
    settings = Settings(database_url=app_db, cookie_secret="x" * 64, cookie_secure=False)
    codec = CookieCodec(settings.cookie_secret)
    user = await _user_with(app_session, [("*", "*")])
    sess = await create_session(
        app_session, user, user_agent="ua", ip="1.2.3.4", ttl_minutes=60
    )
    await app_session.commit()
    await _seed_job_rets(app_session)

    app = create_app(settings=settings, codec=codec)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
        r = await ac.get(
            "/api/activity",
            cookies={settings.cookie_name: codec.sign(sess.id)},
        )
    assert r.status_code == 200, r.text
    assert r.json()["total"] == 4


@pytest.mark.asyncio
async def test_since_minutes_bounds_by_time(app_db, app_session):
    """since_minutes only returns rows newer than the cutoff."""
    settings = Settings(database_url=app_db, cookie_secret="x" * 64, cookie_secure=False)
    codec = CookieCodec(settings.cookie_secret)
    user = await _user_with(app_session, [("*", "*")])
    sess = await create_session(
        app_session, user, user_agent="ua", ip="1.2.3.4", ttl_minutes=60
    )
    await app_session.commit()

    now = datetime.now(tz=UTC)
    recent = ActivityEvent(
        ts=now,
        category="job",
        event_type="job.ret",
        minion_id="recent-1",
        jid="20260527000000000010",
        fun="state.highstate",
        success=True,
        changed=True,
        summary="recent-1 returned state.highstate ✓",
    )
    old = ActivityEvent(
        ts=now - timedelta(hours=3),
        category="job",
        event_type="job.ret",
        minion_id="old-1",
        jid="20260527000000000011",
        fun="state.highstate",
        success=True,
        changed=True,
        summary="old-1 returned state.highstate ✓",
    )
    app_session.add(recent)
    app_session.add(old)
    await app_session.commit()

    app = create_app(settings=settings, codec=codec)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
        r = await ac.get(
            "/api/activity?since_minutes=60",
            cookies={settings.cookie_name: codec.sign(sess.id)},
        )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["total"] == 1
    assert {e["minion_id"] for e in body["events"]} == {"recent-1"}
