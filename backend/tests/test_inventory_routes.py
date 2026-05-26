# backend/tests/test_inventory_routes.py
"""Route-layer tests for /api/inventory/*.

Covers:
  * /packages/search — name/source/minion filters, version filter, RBAC.
  * /refresh         — happy path, salt-unavailable, RBAC, audit row written.

These tests share the DB + fake-salt-api fixture pattern used by the rest
of the test suite (see backend/tests/test_run_routes.py for the canonical
example).
"""

from __future__ import annotations

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
from halite.inventory.models import InventoryPackage, InventorySnapshot
from halite.main import create_app
from halite.rbac.models import Permission, Role, UserRole
from halite.salt.client import SaltAPIClient

# ---------- DB fixtures ----------


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
    role = Role(name="inv-test", is_builtin=False, description="")
    session.add(role)
    await session.flush()
    for verb, glob in perms:
        session.add(Permission(role_id=role.id, verb=verb, resource_glob=glob))
    session.add(UserRole(user_id=user.id, role_id=role.id))
    await session.commit()
    await session.refresh(user)
    return user


async def _seed_packages(session) -> None:
    """Populate the DB with a small fleet for the search tests:

    * web-01 (apt):   openssh-server 1:8.9p1-3ubuntu0.4, vim 2:9.0
    * db-01  (rpm):   openssh-server 8.0p1-13.el8, bash 4.4.20-4.el8
    * old-01 (rpm):   openssh-server 1.5.0-1.el5   <-- the "vulnerable" host
    """
    now = datetime.now(tz=UTC)
    rows = [
        ("web-01", "openssh-server", "1:8.9p1-3ubuntu0.4", "amd64", "apt"),
        ("web-01", "vim", "2:9.0", None, "apt"),
        ("db-01", "openssh-server", "8.0p1-13.el8", None, "rpm"),
        ("db-01", "bash", "4.4.20-4.el8", None, "rpm"),
        ("old-01", "openssh-server", "1.5.0-1.el5", None, "rpm"),
    ]
    for mid, name, ver, arch, src in rows:
        session.add(
            InventoryPackage(
                minion_id=mid,
                name=name,
                version=ver,
                arch=arch,
                source=src,
                collected_at=now,
            )
        )
    for mid, count in (("web-01", 2), ("db-01", 2), ("old-01", 1)):
        session.add(
            InventorySnapshot(
                minion_id=mid,
                facet="packages",
                collected_at=now,
                salt_jid=None,
                item_count=count,
            )
        )
    await session.commit()


def _attach_salt_client(app, fake_salt_api) -> SaltAPIClient:
    client = SaltAPIClient(
        base_url="http://salt.test",
        username="halite-service",
        password="pw",
        transport=fake_salt_api.transport,
    )
    app.state.salt_client = client
    return client


# ---------- /packages/search ----------


@pytest.mark.asyncio
async def test_search_packages_by_name_eq(app_db, session):
    settings = Settings(database_url=app_db, cookie_secret="x" * 64, cookie_secure=False)
    codec = CookieCodec(settings.cookie_secret)
    user = await _user_with(session, [("view", "inventory:*")])
    sess = await create_session(session, user, user_agent="ua", ip="1.2.3.4", ttl_minutes=60)
    await session.commit()
    await _seed_packages(session)

    app = create_app(settings=settings, codec=codec)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
        r = await ac.post(
            "/api/inventory/packages/search",
            cookies={settings.cookie_name: codec.sign(sess.id)},
            json={"name": {"op": "eq", "value": "openssh-server"}},
        )

    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 3
    assert {hit["minion_id"] for hit in body["hits"]} == {"web-01", "db-01", "old-01"}


@pytest.mark.asyncio
async def test_search_packages_with_version_lte_finds_vulnerable_host(app_db, session):
    """The user's motivating example: openssh-server <= 2.1.0 should find
    old-01 and only old-01 — including across mixed apt/rpm minions."""
    settings = Settings(database_url=app_db, cookie_secret="x" * 64, cookie_secure=False)
    codec = CookieCodec(settings.cookie_secret)
    user = await _user_with(session, [("view", "inventory:*")])
    sess = await create_session(session, user, user_agent="ua", ip="1.2.3.4", ttl_minutes=60)
    await session.commit()
    await _seed_packages(session)

    app = create_app(settings=settings, codec=codec)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
        r = await ac.post(
            "/api/inventory/packages/search",
            cookies={settings.cookie_name: codec.sign(sess.id)},
            json={
                "name": {"op": "eq", "value": "openssh-server"},
                "version": {"op": "lte", "value": "2.1.0"},
            },
        )

    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 1
    assert body["hits"][0]["minion_id"] == "old-01"
    assert body["hits"][0]["version"] == "1.5.0-1.el5"


@pytest.mark.asyncio
async def test_search_packages_filters_by_source(app_db, session):
    settings = Settings(database_url=app_db, cookie_secret="x" * 64, cookie_secure=False)
    codec = CookieCodec(settings.cookie_secret)
    user = await _user_with(session, [("view", "inventory:*")])
    sess = await create_session(session, user, user_agent="ua", ip="1.2.3.4", ttl_minutes=60)
    await session.commit()
    await _seed_packages(session)

    app = create_app(settings=settings, codec=codec)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
        r = await ac.post(
            "/api/inventory/packages/search",
            cookies={settings.cookie_name: codec.sign(sess.id)},
            json={"name": {"op": "eq", "value": "openssh-server"}, "source": "apt"},
        )

    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 1
    assert body["hits"][0]["minion_id"] == "web-01"


@pytest.mark.asyncio
async def test_search_packages_by_minion_only(app_db, session):
    """A minion-only filter returns that minion's full package list — this is
    what the /minions/{id} packages tab calls."""
    settings = Settings(database_url=app_db, cookie_secret="x" * 64, cookie_secure=False)
    codec = CookieCodec(settings.cookie_secret)
    user = await _user_with(session, [("view", "inventory:*")])
    sess = await create_session(session, user, user_agent="ua", ip="1.2.3.4", ttl_minutes=60)
    await session.commit()
    await _seed_packages(session)

    app = create_app(settings=settings, codec=codec)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
        r = await ac.post(
            "/api/inventory/packages/search",
            cookies={settings.cookie_name: codec.sign(sess.id)},
            json={"minion_id": "web-01"},
        )

    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 2
    assert {h["name"] for h in body["hits"]} == {"openssh-server", "vim"}


@pytest.mark.asyncio
async def test_search_packages_name_prefix(app_db, session):
    settings = Settings(database_url=app_db, cookie_secret="x" * 64, cookie_secure=False)
    codec = CookieCodec(settings.cookie_secret)
    user = await _user_with(session, [("view", "inventory:*")])
    sess = await create_session(session, user, user_agent="ua", ip="1.2.3.4", ttl_minutes=60)
    await session.commit()
    await _seed_packages(session)

    app = create_app(settings=settings, codec=codec)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
        r = await ac.post(
            "/api/inventory/packages/search",
            cookies={settings.cookie_name: codec.sign(sess.id)},
            json={"name": {"op": "prefix", "value": "openssh"}},
        )
    assert r.status_code == 200
    assert r.json()["total"] == 3


@pytest.mark.asyncio
async def test_search_packages_rejects_empty_filter(app_db, session):
    """At least one of name/minion_id is required — guardrail against
    accidentally fetching the entire fleet."""
    settings = Settings(database_url=app_db, cookie_secret="x" * 64, cookie_secure=False)
    codec = CookieCodec(settings.cookie_secret)
    user = await _user_with(session, [("view", "inventory:*")])
    sess = await create_session(session, user, user_agent="ua", ip="1.2.3.4", ttl_minutes=60)
    await session.commit()

    app = create_app(settings=settings, codec=codec)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
        r = await ac.post(
            "/api/inventory/packages/search",
            cookies={settings.cookie_name: codec.sign(sess.id)},
            json={"version": {"op": "lte", "value": "1.0"}},
        )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_search_packages_403_without_view_inventory(app_db, session):
    settings = Settings(database_url=app_db, cookie_secret="x" * 64, cookie_secure=False)
    codec = CookieCodec(settings.cookie_secret)
    user = await _user_with(session, [("view", "minion:*")])  # not inventory
    sess = await create_session(session, user, user_agent="ua", ip="1.2.3.4", ttl_minutes=60)
    await session.commit()

    app = create_app(settings=settings, codec=codec)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
        r = await ac.post(
            "/api/inventory/packages/search",
            cookies={settings.cookie_name: codec.sign(sess.id)},
            json={"name": {"op": "eq", "value": "openssh-server"}},
        )
    assert r.status_code == 403


# ---------- /refresh ----------


def _refresh_handler():
    def handler(payload):
        fun = payload.get("fun")
        if fun == "pkg.list_pkgs":
            return {"return": [{"web-01": {"vim": "2:9.0"}}]}
        if fun == "grains.get":
            return {"return": [{"web-01": "Debian"}]}
        return {"return": [{}]}

    return handler


@pytest.mark.asyncio
async def test_refresh_happy_path_audits_and_writes(app_db, session, fake_salt_api):
    settings = Settings(database_url=app_db, cookie_secret="x" * 64, cookie_secure=False)
    codec = CookieCodec(settings.cookie_secret)
    user = await _user_with(session, [("collect", "inventory:*")])
    sess = await create_session(session, user, user_agent="ua", ip="1.2.3.4", ttl_minutes=60)
    await session.commit()

    fake_salt_api.run_handler = _refresh_handler()

    app = create_app(settings=settings, codec=codec)
    client = _attach_salt_client(app, fake_salt_api)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
            r = await ac.post(
                "/api/inventory/refresh",
                cookies={settings.cookie_name: codec.sign(sess.id)},
                json={"target": "*"},
            )
    finally:
        await client.aclose()

    assert r.status_code == 200
    body = r.json()
    assert body == {"minions_refreshed": 1, "package_counts": {"web-01": 1}}

    # Inventory was written.
    pkgs = (await session.execute(select(InventoryPackage))).scalars().all()
    assert len(pkgs) == 1
    assert pkgs[0].minion_id == "web-01"

    # An audit row was written with decision=allow.
    audit = (
        (await session.execute(select(AuditEntry).where(AuditEntry.action == "inventory.refresh")))
        .scalars()
        .all()
    )
    assert len(audit) == 1
    assert audit[0].decision == "allow"
    assert audit[0].result_code == 200
    # The args_json captures both the request body and the affected minions.
    assert audit[0].args_json["target"] == "*"
    assert audit[0].args_json["minions"] == ["web-01"]


@pytest.mark.asyncio
async def test_refresh_403_without_collect_perm(app_db, session, fake_salt_api):
    settings = Settings(database_url=app_db, cookie_secret="x" * 64, cookie_secure=False)
    codec = CookieCodec(settings.cookie_secret)
    user = await _user_with(session, [("view", "inventory:*")])  # view only
    sess = await create_session(session, user, user_agent="ua", ip="1.2.3.4", ttl_minutes=60)
    await session.commit()

    fake_salt_api.run_handler = _refresh_handler()

    app = create_app(settings=settings, codec=codec)
    client = _attach_salt_client(app, fake_salt_api)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
            r = await ac.post(
                "/api/inventory/refresh",
                cookies={settings.cookie_name: codec.sign(sess.id)},
                json={"target": "*"},
            )
    finally:
        await client.aclose()
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_refresh_503_when_salt_not_configured(app_db, session):
    """No salt client attached → /refresh is 503 (same shape as /api/minions)."""
    settings = Settings(database_url=app_db, cookie_secret="x" * 64, cookie_secure=False)
    codec = CookieCodec(settings.cookie_secret)
    user = await _user_with(session, [("collect", "inventory:*")])
    sess = await create_session(session, user, user_agent="ua", ip="1.2.3.4", ttl_minutes=60)
    await session.commit()

    app = create_app(settings=settings, codec=codec)
    async with (
        AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac,
        app.router.lifespan_context(app),
    ):
        r = await ac.post(
            "/api/inventory/refresh",
            cookies={settings.cookie_name: codec.sign(sess.id)},
            json={"target": "*"},
        )
    assert r.status_code == 503


# ---------- /packages (aggregate) ----------


@pytest.mark.asyncio
async def test_list_packages_aggregate_no_filter_returns_all_names(app_db, session):
    """Landing view: no filter, list every distinct package across the fleet.
    Each row carries minion_count and version_count."""
    settings = Settings(database_url=app_db, cookie_secret="x" * 64, cookie_secure=False)
    codec = CookieCodec(settings.cookie_secret)
    user = await _user_with(session, [("view", "inventory:*")])
    sess = await create_session(session, user, user_agent="ua", ip="1.2.3.4", ttl_minutes=60)
    await session.commit()
    await _seed_packages(session)

    app = create_app(settings=settings, codec=codec)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
        r = await ac.get(
            "/api/inventory/packages",
            cookies={settings.cookie_name: codec.sign(sess.id)},
        )
    assert r.status_code == 200
    body = r.json()
    # The seed has bash, openssh-server, and vim across three minions.
    by_name = {item["name"]: item for item in body["items"]}
    assert body["total"] == 3
    assert set(by_name) == {"bash", "openssh-server", "vim"}
    # openssh-server is on web-01, db-01, and old-01 — three different versions.
    ossh = by_name["openssh-server"]
    assert ossh["minion_count"] == 3
    assert ossh["version_count"] == 3
    # vim is only on web-01, one version.
    assert by_name["vim"]["minion_count"] == 1
    assert by_name["vim"]["version_count"] == 1


@pytest.mark.asyncio
async def test_list_packages_aggregate_q_substring_filter(app_db, session):
    settings = Settings(database_url=app_db, cookie_secret="x" * 64, cookie_secure=False)
    codec = CookieCodec(settings.cookie_secret)
    user = await _user_with(session, [("view", "inventory:*")])
    sess = await create_session(session, user, user_agent="ua", ip="1.2.3.4", ttl_minutes=60)
    await session.commit()
    await _seed_packages(session)

    app = create_app(settings=settings, codec=codec)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
        r = await ac.get(
            "/api/inventory/packages",
            params={"q": "ssh"},
            cookies={settings.cookie_name: codec.sign(sess.id)},
        )
    assert r.status_code == 200
    body = r.json()
    assert [it["name"] for it in body["items"]] == ["openssh-server"]
    assert body["total"] == 1


@pytest.mark.asyncio
async def test_list_packages_aggregate_source_filter(app_db, session):
    settings = Settings(database_url=app_db, cookie_secret="x" * 64, cookie_secure=False)
    codec = CookieCodec(settings.cookie_secret)
    user = await _user_with(session, [("view", "inventory:*")])
    sess = await create_session(session, user, user_agent="ua", ip="1.2.3.4", ttl_minutes=60)
    await session.commit()
    await _seed_packages(session)

    app = create_app(settings=settings, codec=codec)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
        r = await ac.get(
            "/api/inventory/packages",
            params={"source": "apt"},
            cookies={settings.cookie_name: codec.sign(sess.id)},
        )
    assert r.status_code == 200
    body = r.json()
    # Only the apt rows contribute: web-01's openssh-server and vim.
    by_name = {item["name"]: item for item in body["items"]}
    assert set(by_name) == {"openssh-server", "vim"}
    assert by_name["openssh-server"]["minion_count"] == 1


@pytest.mark.asyncio
async def test_list_packages_aggregate_403_without_view(app_db, session):
    settings = Settings(database_url=app_db, cookie_secret="x" * 64, cookie_secure=False)
    codec = CookieCodec(settings.cookie_secret)
    user = await _user_with(session, [("view", "minion:*")])  # not inventory
    sess = await create_session(session, user, user_agent="ua", ip="1.2.3.4", ttl_minutes=60)
    await session.commit()

    app = create_app(settings=settings, codec=codec)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
        r = await ac.get(
            "/api/inventory/packages",
            cookies={settings.cookie_name: codec.sign(sess.id)},
        )
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_list_packages_aggregate_pagination(app_db, session):
    settings = Settings(database_url=app_db, cookie_secret="x" * 64, cookie_secure=False)
    codec = CookieCodec(settings.cookie_secret)
    user = await _user_with(session, [("view", "inventory:*")])
    sess = await create_session(session, user, user_agent="ua", ip="1.2.3.4", ttl_minutes=60)
    await session.commit()
    await _seed_packages(session)

    app = create_app(settings=settings, codec=codec)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
        first = await ac.get(
            "/api/inventory/packages",
            params={"limit": 2, "offset": 0},
            cookies={settings.cookie_name: codec.sign(sess.id)},
        )
        second = await ac.get(
            "/api/inventory/packages",
            params={"limit": 2, "offset": 2},
            cookies={settings.cookie_name: codec.sign(sess.id)},
        )
    assert first.status_code == 200
    assert second.status_code == 200
    # Total is constant across pages.
    assert first.json()["total"] == 3
    assert second.json()["total"] == 3
    # Pages are disjoint and complete.
    page1 = [it["name"] for it in first.json()["items"]]
    page2 = [it["name"] for it in second.json()["items"]]
    assert len(page1) == 2
    assert len(page2) == 1
    assert set(page1 + page2) == {"bash", "openssh-server", "vim"}


# ---------- /packages/{name}/versions ----------


@pytest.mark.asyncio
async def test_list_versions_returns_per_version_minion_counts(app_db, session):
    settings = Settings(database_url=app_db, cookie_secret="x" * 64, cookie_secure=False)
    codec = CookieCodec(settings.cookie_secret)
    user = await _user_with(session, [("view", "inventory:*")])
    sess = await create_session(session, user, user_agent="ua", ip="1.2.3.4", ttl_minutes=60)
    await session.commit()
    await _seed_packages(session)

    app = create_app(settings=settings, codec=codec)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
        r = await ac.get(
            "/api/inventory/packages/openssh-server/versions",
            cookies={settings.cookie_name: codec.sign(sess.id)},
        )
    assert r.status_code == 200
    body = r.json()
    assert body["name"] == "openssh-server"
    assert body["total"] == 3
    versions = {item["version"]: item for item in body["items"]}
    assert set(versions) == {"1:8.9p1-3ubuntu0.4", "8.0p1-13.el8", "1.5.0-1.el5"}
    # Each version has one minion in the seed data.
    for v in versions.values():
        assert v["minion_count"] == 1
    # The amd64 arch is preserved for the apt row.
    apt_row = versions["1:8.9p1-3ubuntu0.4"]
    assert apt_row["arch"] == "amd64"
    assert apt_row["source"] == "apt"


@pytest.mark.asyncio
async def test_list_versions_orders_dominant_first(app_db, session):
    """When multiple minions share a version, that version should sort first."""
    settings = Settings(database_url=app_db, cookie_secret="x" * 64, cookie_secure=False)
    codec = CookieCodec(settings.cookie_secret)
    user = await _user_with(session, [("view", "inventory:*")])
    sess = await create_session(session, user, user_agent="ua", ip="1.2.3.4", ttl_minutes=60)
    await session.commit()

    # Three minions on v1, one on v2.
    from datetime import UTC, datetime

    now = datetime.now(tz=UTC)
    for mid in ("web-01", "web-02", "web-03"):
        session.add(
            InventoryPackage(
                minion_id=mid,
                name="nginx",
                version="1.18.0",
                arch=None,
                source="apt",
                collected_at=now,
            )
        )
    session.add(
        InventoryPackage(
            minion_id="web-04",
            name="nginx",
            version="1.20.0",
            arch=None,
            source="apt",
            collected_at=now,
        )
    )
    await session.commit()

    app = create_app(settings=settings, codec=codec)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
        r = await ac.get(
            "/api/inventory/packages/nginx/versions",
            cookies={settings.cookie_name: codec.sign(sess.id)},
        )
    body = r.json()
    versions = [it["version"] for it in body["items"]]
    assert versions == ["1.18.0", "1.20.0"]  # dominant first


@pytest.mark.asyncio
async def test_list_versions_returns_empty_for_unknown_package(app_db, session):
    settings = Settings(database_url=app_db, cookie_secret="x" * 64, cookie_secure=False)
    codec = CookieCodec(settings.cookie_secret)
    user = await _user_with(session, [("view", "inventory:*")])
    sess = await create_session(session, user, user_agent="ua", ip="1.2.3.4", ttl_minutes=60)
    await session.commit()

    app = create_app(settings=settings, codec=codec)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
        r = await ac.get(
            "/api/inventory/packages/nonexistent/versions",
            cookies={settings.cookie_name: codec.sign(sess.id)},
        )
    assert r.status_code == 200
    body = r.json()
    assert body["name"] == "nonexistent"
    assert body["total"] == 0
    assert body["items"] == []


# ---------- /refresh sad paths (existing) ----------


@pytest.mark.asyncio
async def test_refresh_502_when_no_minion_responds(app_db, session, fake_salt_api):
    """Salt-api answered, but no minion produced usable data — surface as 502."""
    settings = Settings(database_url=app_db, cookie_secret="x" * 64, cookie_secure=False)
    codec = CookieCodec(settings.cookie_secret)
    user = await _user_with(session, [("collect", "inventory:*")])
    sess = await create_session(session, user, user_agent="ua", ip="1.2.3.4", ttl_minutes=60)
    await session.commit()

    def empty_handler(payload):
        return {"return": [{}]}  # all minions silent

    fake_salt_api.run_handler = empty_handler

    app = create_app(settings=settings, codec=codec)
    client = _attach_salt_client(app, fake_salt_api)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
            r = await ac.post(
                "/api/inventory/refresh",
                cookies={settings.cookie_name: codec.sign(sess.id)},
                json={"target": "*"},
            )
    finally:
        await client.aclose()
    assert r.status_code == 502
