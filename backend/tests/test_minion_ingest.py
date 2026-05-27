from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select

from halite.minions.ingest import (
    refresh_grains,
    refresh_keys,
    refresh_presence,
)
from halite.minions.snapshot_model import MinionSnapshot


@pytest.mark.asyncio
async def test_refresh_keys_inserts_rows_for_new_keys_and_updates_status(session):
    salt = AsyncMock()
    salt.list_minion_keys.return_value = {
        "minions": ["web-1"],
        "minions_pre": ["pending-1"],
        "minions_rejected": ["rejected-1"],
        "minions_denied": [],
    }
    await refresh_keys(session, salt)
    await session.commit()
    rows = (await session.execute(select(MinionSnapshot))).scalars().all()
    by_id = {r.minion_id: r for r in rows}
    assert by_id["web-1"].key_status == "accepted"
    assert by_id["pending-1"].key_status == "pending"
    assert by_id["rejected-1"].key_status == "rejected"
    assert by_id["web-1"].keys_refreshed_at is not None
    assert by_id["web-1"].presence_refreshed_at is None
    assert by_id["web-1"].grains_refreshed_at is None


@pytest.mark.asyncio
async def test_refresh_keys_marks_minion_offline_when_key_disappears(session):
    salt = AsyncMock()
    salt.list_minion_keys.return_value = {
        "minions": ["web-1"],
        "minions_pre": [],
        "minions_rejected": [],
        "minions_denied": [],
    }
    await refresh_keys(session, salt)
    await session.commit()

    salt.list_minion_keys.return_value = {
        "minions": [],
        "minions_pre": [],
        "minions_rejected": [],
        "minions_denied": [],
    }
    await refresh_keys(session, salt)
    await session.commit()
    rows = (await session.execute(select(MinionSnapshot))).scalars().all()
    assert rows == []


@pytest.mark.asyncio
async def test_refresh_presence_creates_rows_and_marks_online(session):
    salt = AsyncMock()
    salt.list_minion_keys.return_value = {
        "minions": ["web-1", "web-2", "db-1"],
        "minions_pre": [],
        "minions_rejected": [],
        "minions_denied": [],
    }
    salt.list_present_minion_ids.return_value = {"web-1", "web-2"}

    await refresh_keys(session, salt)
    await refresh_presence(session, salt)
    await session.commit()

    rows = (await session.execute(select(MinionSnapshot))).scalars().all()
    by_id = {r.minion_id: r for r in rows}
    assert set(by_id) == {"web-1", "web-2", "db-1"}
    assert by_id["web-1"].online is True
    assert by_id["db-1"].online is False
    assert by_id["web-1"].presence_refreshed_at is not None


@pytest.mark.asyncio
async def test_refresh_grains_populates_denormalized_fields(session):
    salt = AsyncMock()
    salt.list_minion_keys.return_value = {
        "minions": ["web-1"],
        "minions_pre": [],
        "minions_rejected": [],
        "minions_denied": [],
    }
    salt.cache_grains.return_value = {
        "web-1": {
            "os": "Ubuntu",
            "os_family": "Debian",
            "osrelease": "22.04",
            "kernel": "Linux",
            "kernelrelease": "5.15.0-1066-aws",
            "virtual": "kvm",
            "num_cpus": 4,
            "mem_total": 7976,
            "saltversion": "3006.5",
            "ip4_gw": "10.0.0.1",
            "ip4_interfaces": {
                "eth0": ["10.0.0.42"],
                "docker0": ["172.17.0.1"],
            },
        },
    }
    await refresh_keys(session, salt)
    await refresh_grains(session, salt)
    await session.commit()

    row = (
        await session.execute(select(MinionSnapshot).where(MinionSnapshot.minion_id == "web-1"))
    ).scalar_one()
    assert row.os == "Ubuntu"
    assert row.os_family == "Debian"
    assert row.kernel == "Linux"
    assert row.num_cpus == 4
    assert row.mem_total_mb == 7976
    assert row.primary_ip == "10.0.0.42"
    assert row.grains["os"] == "Ubuntu"
    assert row.grains_refreshed_at is not None
