from __future__ import annotations

import asyncio
import types
from datetime import UTC, datetime

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from halite.activity.hub import EventHub
from halite.auth.cookies import CookieCodec
from halite.auth.models import User
from halite.auth.password import hash_password
from halite.auth.service import create_session
from halite.config import Settings
from halite.main import create_app
from halite.rbac.models import Permission, Role, UserRole


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
    role = Role(name="activity-stream-test", is_builtin=False, description="")
    session.add(role)
    await session.flush()
    for verb, glob in perms:
        session.add(Permission(role_id=role.id, verb=verb, resource_glob=glob))
    session.add(UserRole(user_id=user.id, role_id=role.id))
    await session.commit()
    await session.refresh(user)
    return user


async def _authed(app_db, app_session, perms):
    """Build the app plus the signed cookie header for an authed user."""
    settings = Settings(database_url=app_db, cookie_secret="x" * 64, cookie_secure=False)
    codec = CookieCodec(settings.cookie_secret)
    user = await _user_with(app_session, perms)
    sess = await create_session(
        app_session, user, user_agent="ua", ip="1.2.3.4", ttl_minutes=60
    )
    await app_session.commit()
    app = create_app(settings=settings, codec=codec)
    cookie = f"{settings.cookie_name}={codec.sign(sess.id)}"
    return app, settings, cookie


def _authed_client(app, settings, cookie):
    return AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://t",
        headers={"cookie": cookie},
    )


async def _drive_sse(app, cookie, *, max_chunks: int = 50):
    """Drive the ASGI app directly for the SSE route.

    httpx's ASGITransport buffers the whole response before yielding, which
    deadlocks against an endless generator. Driving the ASGI app ourselves
    lets us collect the immediate ring-buffer replay and then send an
    `http.disconnect` so the generator's read loop exits cleanly.
    """
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": "/api/activity/stream",
        "raw_path": b"/api/activity/stream",
        "query_string": b"",
        "headers": [(b"host", b"t"), (b"cookie", cookie.encode())],
        "client": ("1.2.3.4", 12345),
        "server": ("t", 80),
    }

    incoming: asyncio.Queue = asyncio.Queue()
    await incoming.put({"type": "http.request", "body": b"", "more_body": False})

    status_code: dict = {}
    chunks: list[bytes] = []
    done = asyncio.Event()

    async def receive():
        return await incoming.get()

    async def send(message):
        if message["type"] == "http.response.start":
            status_code["code"] = message["status"]
        elif message["type"] == "http.response.body":
            body = message.get("body", b"")
            if body:
                chunks.append(body)
            # After the replay flushes, ask the app to disconnect so the
            # endless live-queue loop exits and the task can finish.
            if len(chunks) >= 1 and not done.is_set():
                done.set()
                await incoming.put({"type": "http.disconnect"})

    task = asyncio.create_task(app(scope, receive, send))
    try:
        await asyncio.wait_for(task, timeout=10.0)
    except TimeoutError:
        task.cancel()
    return status_code.get("code"), b"".join(chunks).decode()


async def test_stream_replays_ring_filtered(app_db, app_session):
    app, _settings, cookie = await _authed(app_db, app_session, [("view", "job:*")])
    hub = EventHub()
    hub.publish(
        {
            "category": "job",
            "event_type": "job.new",
            "summary": "j",
            "minion_id": None,
            "jid": "1",
            "fun": "x",
            "success": None,
        }
    )
    hub.publish(
        {
            "category": "key",
            "event_type": "key.accept",
            "summary": "k",
            "minion_id": "d",
            "jid": None,
            "fun": None,
            "success": None,
        }
    )
    app.state.runtime = types.SimpleNamespace(event_hub=hub)

    code, body = await _drive_sse(app, cookie)
    assert code == 200
    assert "job.new" in body
    assert "key.accept" not in body
    # The subscriber queue should be cleaned up after disconnect.
    assert hub._subscribers == set()


async def test_stream_forbidden_without_perms(app_db, app_session):
    app, settings, cookie = await _authed(app_db, app_session, [("view", "settings:*")])
    app.state.runtime = types.SimpleNamespace(event_hub=EventHub())
    async with _authed_client(app, settings, cookie) as ac:
        r = await ac.get("/api/activity/stream")
    assert r.status_code == 403, r.text


async def test_stream_503_without_hub(app_db, app_session):
    app, settings, cookie = await _authed(app_db, app_session, [("view", "job:*")])
    app.state.runtime = types.SimpleNamespace(event_hub=None)
    async with _authed_client(app, settings, cookie) as ac:
        r = await ac.get("/api/activity/stream")
    assert r.status_code == 503, r.text
