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


def _payload(name: str = "Web dry-run highstate", **overrides):
    body = {
        "name": name,
        "description": "Dry-run the highstate on every web minion",
        "target": "web-*",
        "target_type": "glob",
        "fun": "state.highstate",
        "args": [],
        "kwargs": {"test": "True"},
    }
    body.update(overrides)
    return body


@pytest.mark.asyncio
async def test_create_template_201_and_audit(app_db, session):
    settings = Settings(database_url=app_db, cookie_secret="x" * 64, cookie_secure=False)
    codec = CookieCodec(settings.cookie_secret)
    user = await _user(session, "alice")
    sess = await create_session(session, user, user_agent="ua", ip="1.2.3.4", ttl_minutes=60)
    await session.commit()

    app = create_app(settings=settings, codec=codec)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
        r = await ac.post(
            "/api/templates",
            cookies={settings.cookie_name: codec.sign(sess.id)},
            json=_payload(),
        )
    assert r.status_code == 201
    body = r.json()
    assert body["name"] == "Web dry-run highstate"
    assert body["fun"] == "state.highstate"

    rows = (
        await session.execute(select(AuditEntry).where(AuditEntry.action == "template.create"))
    ).scalars().all()
    assert len(rows) == 1
    assert rows[0].decision == "allow"


@pytest.mark.asyncio
async def test_list_own_returns_user_templates_only(app_db, session):
    settings = Settings(database_url=app_db, cookie_secret="x" * 64, cookie_secure=False)
    codec = CookieCodec(settings.cookie_secret)
    alice = await _user(session, "alice")
    bob = await _user(session, "bob")
    alice_sess = await create_session(session, alice, user_agent="ua", ip="1.2.3.4", ttl_minutes=60)
    bob_sess = await create_session(session, bob, user_agent="ua", ip="1.2.3.4", ttl_minutes=60)
    await session.commit()

    app = create_app(settings=settings, codec=codec)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
        r1 = await ac.post(
            "/api/templates",
            cookies={settings.cookie_name: codec.sign(alice_sess.id)},
            json=_payload(name="Alice's template"),
        )
        assert r1.status_code == 201
        r2 = await ac.post(
            "/api/templates",
            cookies={settings.cookie_name: codec.sign(bob_sess.id)},
            json=_payload(name="Bob's template"),
        )
        assert r2.status_code == 201
        r3 = await ac.get(
            "/api/templates",
            cookies={settings.cookie_name: codec.sign(alice_sess.id)},
        )
    body = r3.json()
    names = [t["name"] for t in body["templates"]]
    assert names == ["Alice's template"]


@pytest.mark.asyncio
async def test_create_409_on_duplicate_name(app_db, session):
    settings = Settings(database_url=app_db, cookie_secret="x" * 64, cookie_secure=False)
    codec = CookieCodec(settings.cookie_secret)
    user = await _user(session, "alice")
    sess = await create_session(session, user, user_agent="ua", ip="1.2.3.4", ttl_minutes=60)
    await session.commit()

    app = create_app(settings=settings, codec=codec)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
        r1 = await ac.post(
            "/api/templates",
            cookies={settings.cookie_name: codec.sign(sess.id)},
            json=_payload(name="Dup"),
        )
        r2 = await ac.post(
            "/api/templates",
            cookies={settings.cookie_name: codec.sign(sess.id)},
            json=_payload(name="Dup"),
        )
    assert r1.status_code == 201
    assert r2.status_code == 409


@pytest.mark.asyncio
async def test_delete_own_204_and_audit(app_db, session):
    settings = Settings(database_url=app_db, cookie_secret="x" * 64, cookie_secure=False)
    codec = CookieCodec(settings.cookie_secret)
    user = await _user(session, "alice")
    sess = await create_session(session, user, user_agent="ua", ip="1.2.3.4", ttl_minutes=60)
    await session.commit()

    app = create_app(settings=settings, codec=codec)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
        r = await ac.post(
            "/api/templates",
            cookies={settings.cookie_name: codec.sign(sess.id)},
            json=_payload(),
        )
        tpl_id = r.json()["id"]
        r2 = await ac.delete(
            f"/api/templates/{tpl_id}",
            cookies={settings.cookie_name: codec.sign(sess.id)},
        )
    assert r2.status_code == 204

    rows = (
        await session.execute(select(AuditEntry).where(AuditEntry.action == "template.delete"))
    ).scalars().all()
    assert len(rows) == 1
    assert rows[0].resource == f"template:{tpl_id}"
    assert rows[0].decision == "allow"


@pytest.mark.asyncio
async def test_delete_other_users_template_returns_404(app_db, session):
    settings = Settings(database_url=app_db, cookie_secret="x" * 64, cookie_secure=False)
    codec = CookieCodec(settings.cookie_secret)
    alice = await _user(session, "alice")
    bob = await _user(session, "bob")
    alice_sess = await create_session(session, alice, user_agent="ua", ip="1.2.3.4", ttl_minutes=60)
    bob_sess = await create_session(session, bob, user_agent="ua", ip="1.2.3.4", ttl_minutes=60)
    await session.commit()

    app = create_app(settings=settings, codec=codec)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
        r1 = await ac.post(
            "/api/templates",
            cookies={settings.cookie_name: codec.sign(alice_sess.id)},
            json=_payload(name="Alice's only"),
        )
        tpl_id = r1.json()["id"]
        r2 = await ac.delete(
            f"/api/templates/{tpl_id}",
            cookies={settings.cookie_name: codec.sign(bob_sess.id)},
        )
    assert r2.status_code == 404


@pytest.mark.asyncio
async def test_list_empty_for_new_user(app_db, session):
    settings = Settings(database_url=app_db, cookie_secret="x" * 64, cookie_secure=False)
    codec = CookieCodec(settings.cookie_secret)
    user = await _user(session, "alice")
    sess = await create_session(session, user, user_agent="ua", ip="1.2.3.4", ttl_minutes=60)
    await session.commit()

    app = create_app(settings=settings, codec=codec)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
        r = await ac.get(
            "/api/templates",
            cookies={settings.cookie_name: codec.sign(sess.id)},
        )
    assert r.status_code == 200
    assert r.json() == {"total": 0, "templates": []}


@pytest.mark.asyncio
async def test_list_visible_includes_shared_from_others(app_db, session):
    settings = Settings(database_url=app_db, cookie_secret="x" * 64, cookie_secure=False)
    codec = CookieCodec(settings.cookie_secret)
    alice = await _user(session, "alice")
    bob = await _user(session, "bob")
    alice_sess = await create_session(session, alice, user_agent="ua", ip="1.2.3.4", ttl_minutes=60)
    bob_sess = await create_session(session, bob, user_agent="ua", ip="1.2.3.4", ttl_minutes=60)
    await session.commit()

    app = create_app(settings=settings, codec=codec)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
        r1 = await ac.post(
            "/api/templates",
            cookies={settings.cookie_name: codec.sign(alice_sess.id)},
            json=_payload(name="Alice's shared", is_shared=True),
        )
        assert r1.status_code == 201
        r2 = await ac.post(
            "/api/templates",
            cookies={settings.cookie_name: codec.sign(bob_sess.id)},
            json=_payload(name="Bob's private"),
        )
        assert r2.status_code == 201
        r3 = await ac.get(
            "/api/templates",
            cookies={settings.cookie_name: codec.sign(bob_sess.id)},
        )
    body = r3.json()
    names = sorted(t["name"] for t in body["templates"])
    assert names == ["Alice's shared", "Bob's private"]
    by_name = {t["name"]: t for t in body["templates"]}
    assert by_name["Alice's shared"]["owner_username"] == "alice"
    assert by_name["Alice's shared"]["is_shared"] is True
    assert by_name["Bob's private"]["owner_username"] == "bob"
    assert by_name["Bob's private"]["is_shared"] is False


@pytest.mark.asyncio
async def test_list_visible_excludes_others_private(app_db, session):
    settings = Settings(database_url=app_db, cookie_secret="x" * 64, cookie_secure=False)
    codec = CookieCodec(settings.cookie_secret)
    alice = await _user(session, "alice")
    bob = await _user(session, "bob")
    alice_sess = await create_session(session, alice, user_agent="ua", ip="1.2.3.4", ttl_minutes=60)
    bob_sess = await create_session(session, bob, user_agent="ua", ip="1.2.3.4", ttl_minutes=60)
    await session.commit()

    app = create_app(settings=settings, codec=codec)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
        r1 = await ac.post(
            "/api/templates",
            cookies={settings.cookie_name: codec.sign(alice_sess.id)},
            json=_payload(name="Alice's secret"),
        )
        assert r1.status_code == 201
        r2 = await ac.get(
            "/api/templates",
            cookies={settings.cookie_name: codec.sign(bob_sess.id)},
        )
    assert r2.status_code == 200
    assert r2.json()["total"] == 0


@pytest.mark.asyncio
async def test_patch_share_own_template_200(app_db, session):
    settings = Settings(database_url=app_db, cookie_secret="x" * 64, cookie_secure=False)
    codec = CookieCodec(settings.cookie_secret)
    user = await _user(session, "alice")
    sess = await create_session(session, user, user_agent="ua", ip="1.2.3.4", ttl_minutes=60)
    await session.commit()

    app = create_app(settings=settings, codec=codec)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
        r1 = await ac.post(
            "/api/templates",
            cookies={settings.cookie_name: codec.sign(sess.id)},
            json=_payload(),
        )
        tpl_id = r1.json()["id"]
        r2 = await ac.patch(
            f"/api/templates/{tpl_id}",
            cookies={settings.cookie_name: codec.sign(sess.id)},
            json={"is_shared": True},
        )
    assert r2.status_code == 200
    assert r2.json()["is_shared"] is True

    rows = (
        await session.execute(select(AuditEntry).where(AuditEntry.action == "template.share"))
    ).scalars().all()
    assert len(rows) == 1
    assert rows[0].decision == "allow"


@pytest.mark.asyncio
async def test_patch_share_other_users_template_returns_404(app_db, session):
    settings = Settings(database_url=app_db, cookie_secret="x" * 64, cookie_secure=False)
    codec = CookieCodec(settings.cookie_secret)
    alice = await _user(session, "alice")
    bob = await _user(session, "bob")
    alice_sess = await create_session(session, alice, user_agent="ua", ip="1.2.3.4", ttl_minutes=60)
    bob_sess = await create_session(session, bob, user_agent="ua", ip="1.2.3.4", ttl_minutes=60)
    await session.commit()

    app = create_app(settings=settings, codec=codec)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
        r1 = await ac.post(
            "/api/templates",
            cookies={settings.cookie_name: codec.sign(alice_sess.id)},
            json=_payload(name="Alice's only"),
        )
        tpl_id = r1.json()["id"]
        r2 = await ac.patch(
            f"/api/templates/{tpl_id}",
            cookies={settings.cookie_name: codec.sign(bob_sess.id)},
            json={"is_shared": True},
        )
    assert r2.status_code == 404


@pytest.mark.asyncio
async def test_create_with_is_shared_true(app_db, session):
    settings = Settings(database_url=app_db, cookie_secret="x" * 64, cookie_secure=False)
    codec = CookieCodec(settings.cookie_secret)
    user = await _user(session, "alice")
    sess = await create_session(session, user, user_agent="ua", ip="1.2.3.4", ttl_minutes=60)
    await session.commit()

    app = create_app(settings=settings, codec=codec)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
        r = await ac.post(
            "/api/templates",
            cookies={settings.cookie_name: codec.sign(sess.id)},
            json=_payload(name="Born shared", is_shared=True),
        )
    assert r.status_code == 201
    body = r.json()
    assert body["is_shared"] is True
    assert body["owner_username"] == "alice"
