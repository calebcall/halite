# backend/tests/test_inventory_service.py
"""Service-layer tests for ``halite.inventory.service``.

These hit a real (migrated) database via the ``session`` fixture and the
``fake_salt_api`` transport, so they exercise the full collector →
persistence pipeline including the snapshot upsert behaviour.
"""

from __future__ import annotations

import pytest
from sqlalchemy import select

from halite.inventory.models import InventoryPackage, InventorySnapshot
from halite.inventory.service import FACET_PACKAGES, refresh_packages
from halite.salt.client import SaltAPIClient


def _make_client(fake_salt_api) -> SaltAPIClient:
    return SaltAPIClient(
        base_url="http://salt-api.test",
        username="halite-service",
        password="pw",
        eauth="pam",
        transport=fake_salt_api.transport,
    )


def _two_minion_handler():
    """Return a handler giving us:
    web-01 (Debian): openssh-server 1:8.9p1-3, vim 2:9.0
    db-01  (RedHat): openssh-server 8.0p1-13, bash 4.4.20-4.el8
    """

    def handler(payload):
        fun = payload.get("fun")
        if fun == "pkg.list_pkgs":
            return {
                "return": [
                    {
                        "web-01": {
                            "openssh-server": [{"version": "1:8.9p1-3", "arch": "amd64"}],
                            "vim": "2:9.0",
                        },
                        "db-01": {
                            "openssh-server": "8.0p1-13",
                            "bash": "4.4.20-4.el8",
                        },
                    }
                ]
            }
        if fun == "grains.get":
            return {"return": [{"web-01": "Debian", "db-01": "RedHat"}]}
        return {"return": [{}]}

    return handler


@pytest.mark.asyncio
async def test_refresh_packages_writes_rows_and_snapshots(session, fake_salt_api):
    fake_salt_api.run_handler = _two_minion_handler()
    client = _make_client(fake_salt_api)
    try:
        counts = await refresh_packages(session, client, salt_jid="20260525120000000000")
    finally:
        await client.aclose()

    assert counts == {"web-01": 2, "db-01": 2}

    pkgs = (await session.execute(select(InventoryPackage))).scalars().all()
    by_key = {(p.minion_id, p.name, p.arch): p for p in pkgs}
    assert by_key[("web-01", "openssh-server", "amd64")].version == "1:8.9p1-3"
    assert by_key[("web-01", "openssh-server", "amd64")].source == "apt"
    assert by_key[("web-01", "vim", None)].version == "2:9.0"
    assert by_key[("web-01", "vim", None)].source == "apt"
    assert by_key[("db-01", "openssh-server", None)].source == "rpm"
    assert by_key[("db-01", "bash", None)].version == "4.4.20-4.el8"

    snapshots = (await session.execute(select(InventorySnapshot))).scalars().all()
    by_minion = {s.minion_id: s for s in snapshots}
    assert set(by_minion) == {"web-01", "db-01"}
    assert by_minion["web-01"].facet == FACET_PACKAGES
    assert by_minion["web-01"].item_count == 2
    assert by_minion["web-01"].salt_jid == "20260525120000000000"
    assert by_minion["db-01"].item_count == 2


@pytest.mark.asyncio
async def test_refresh_packages_replaces_previous_snapshot(session, fake_salt_api):
    """A second refresh must delete the minion's old rows so packages that
    have been uninstalled don't linger in the inventory."""
    # First refresh — full set.
    fake_salt_api.run_handler = _two_minion_handler()
    client = _make_client(fake_salt_api)
    try:
        await refresh_packages(session, client)

        # Second refresh — web-01 now only reports vim. openssh-server should
        # disappear from the DB.
        def shrink_handler(payload):
            fun = payload.get("fun")
            if fun == "pkg.list_pkgs":
                return {"return": [{"web-01": {"vim": "2:9.1"}}]}
            if fun == "grains.get":
                return {"return": [{"web-01": "Debian"}]}
            return {"return": [{}]}

        fake_salt_api.run_handler = shrink_handler
        await refresh_packages(session, client)
    finally:
        await client.aclose()

    web_pkgs = (
        (
            await session.execute(
                select(InventoryPackage).where(InventoryPackage.minion_id == "web-01")
            )
        )
        .scalars()
        .all()
    )
    assert [(p.name, p.version) for p in web_pkgs] == [("vim", "2:9.1")]

    snap = (
        await session.execute(
            select(InventorySnapshot).where(InventorySnapshot.minion_id == "web-01")
        )
    ).scalar_one()
    assert snap.item_count == 1


@pytest.mark.asyncio
async def test_refresh_packages_offline_minion_keeps_old_data(session, fake_salt_api):
    """If a minion is offline during refresh, its existing rows must stay
    untouched. (Regression: an early version wiped offline minions.)"""
    # Seed web-01 with a snapshot.
    fake_salt_api.run_handler = _two_minion_handler()
    client = _make_client(fake_salt_api)
    try:
        await refresh_packages(session, client)

        # Now web-01 goes offline (False return from salt-api).
        def offline_handler(payload):
            fun = payload.get("fun")
            if fun == "pkg.list_pkgs":
                return {"return": [{"web-01": False, "db-01": {"bash": "4.4.20-5.el8"}}]}
            if fun == "grains.get":
                return {"return": [{"db-01": "RedHat"}]}
            return {"return": [{}]}

        fake_salt_api.run_handler = offline_handler
        counts = await refresh_packages(session, client)
    finally:
        await client.aclose()

    # Only db-01 had a refresh.
    assert counts == {"db-01": 1}

    # web-01's old packages are still in the DB.
    web_pkgs = (
        (
            await session.execute(
                select(InventoryPackage).where(InventoryPackage.minion_id == "web-01")
            )
        )
        .scalars()
        .all()
    )
    assert {p.name for p in web_pkgs} == {"openssh-server", "vim"}

    # db-01 was refreshed and now reflects the new state.
    db_pkgs = (
        (
            await session.execute(
                select(InventoryPackage).where(InventoryPackage.minion_id == "db-01")
            )
        )
        .scalars()
        .all()
    )
    assert [(p.name, p.version) for p in db_pkgs] == [("bash", "4.4.20-5.el8")]


@pytest.mark.asyncio
async def test_refresh_packages_deduplicates_repeated_name_arch(session, fake_salt_api):
    """Salt has been seen to return duplicate (name, arch) pairs when two
    repositories ship the same package. The persistence layer must dedupe
    rather than trip the uniqueness constraint."""

    def handler(payload):
        if payload.get("fun") == "pkg.list_pkgs":
            return {
                "return": [
                    {
                        "web-01": {
                            "libfoo": [
                                {"version": "1.0-1", "arch": "amd64"},
                                {"version": "1.0-2", "arch": "amd64"},
                            ]
                        }
                    }
                ]
            }
        if payload.get("fun") == "grains.get":
            return {"return": [{"web-01": "Debian"}]}
        return {"return": [{}]}

    fake_salt_api.run_handler = handler
    client = _make_client(fake_salt_api)
    try:
        counts = await refresh_packages(session, client)
    finally:
        await client.aclose()

    assert counts == {"web-01": 2}  # the collector returns both entries
    rows = (
        (await session.execute(select(InventoryPackage).where(InventoryPackage.name == "libfoo")))
        .scalars()
        .all()
    )
    # ...but the DB stores exactly one row per (minion, name, arch).
    assert len(rows) == 1
    # Last write wins on the dedupe collision.
    assert rows[0].version == "1.0-2"
