# backend/tests/test_inventory_collectors.py
"""Unit tests for ``halite.inventory.collectors``.

Covers the salt-side response normalisation (the three real-world shapes of
``pkg.list_pkgs``), the ``os_family`` → ``source`` mapping, and the
minion-skip behaviour when salt returns a non-dict (offline / errored
minion).
"""

from __future__ import annotations

import pytest

from halite.inventory.collectors import (
    PackageEntry,
    _classify_source,
    _flatten_pkg_result,
    _flatten_pkg_value,
    collect_packages,
)
from halite.salt.client import SaltAPIClient


def _make_client(fake_salt_api) -> SaltAPIClient:
    return SaltAPIClient(
        base_url="http://salt-api.test",
        username="halite-service",
        password="pw",
        eauth="pam",
        transport=fake_salt_api.transport,
    )


# ---------- _flatten_pkg_value: every shape salt might hand us ----------


def test_flatten_pkg_value_scalar_string():
    assert _flatten_pkg_value("1.2.3-1ubuntu1") == [("1.2.3-1ubuntu1", None)]


def test_flatten_pkg_value_versions_as_list():
    assert _flatten_pkg_value(["1.2.3-1", "1.2.3-2"]) == [
        ("1.2.3-1", None),
        ("1.2.3-2", None),
    ]


def test_flatten_pkg_value_attr_dicts():
    value = [
        {"version": "1.2.3-1ubuntu1", "arch": "amd64"},
        {"version": "1.2.3-1ubuntu1", "arch": "i386"},
    ]
    assert _flatten_pkg_value(value) == [
        ("1.2.3-1ubuntu1", "amd64"),
        ("1.2.3-1ubuntu1", "i386"),
    ]


def test_flatten_pkg_value_drops_empty_entries():
    assert _flatten_pkg_value("") == []
    assert _flatten_pkg_value([{"version": ""}, {"arch": "amd64"}, ""]) == []


def test_flatten_pkg_value_ignores_unknown_shapes():
    assert _flatten_pkg_value(None) == []
    assert _flatten_pkg_value(42) == []
    assert _flatten_pkg_value({"version": "x"}) == []  # dict at top level, not a list


# ---------- _flatten_pkg_result ----------


def test_flatten_pkg_result_mixes_shapes():
    pkg_data = {
        "openssh-server": [{"version": "1:8.9p1-3ubuntu0.4", "arch": "amd64"}],
        "vim": "2:9.0.1378-2",
        "libfoo": ["1.0-1", "1.0-2"],
    }
    result = _flatten_pkg_result(pkg_data)
    assert PackageEntry(name="openssh-server", version="1:8.9p1-3ubuntu0.4", arch="amd64") in result
    assert PackageEntry(name="vim", version="2:9.0.1378-2", arch=None) in result
    assert PackageEntry(name="libfoo", version="1.0-1", arch=None) in result
    assert PackageEntry(name="libfoo", version="1.0-2", arch=None) in result
    assert len(result) == 4


def test_flatten_pkg_result_rejects_non_dict():
    assert _flatten_pkg_result(None) == []
    assert _flatten_pkg_result([]) == []
    assert _flatten_pkg_result("error") == []


# ---------- _classify_source ----------


@pytest.mark.parametrize(
    "os_family,expected",
    [
        ("Debian", "apt"),
        ("RedHat", "rpm"),
        ("Rocky", "rpm"),
        ("AlmaLinux", "rpm"),
        ("Suse", "rpm"),
        ("SUSE", "rpm"),
        ("openSUSE", "rpm"),
        ("Arch", "pacman"),
        ("Gentoo", None),
        ("FreeBSD", None),
        ("", None),
        (None, None),
    ],
)
def test_classify_source(os_family, expected):
    assert _classify_source(os_family) == expected


# ---------- collect_packages end-to-end against fake salt-api ----------


@pytest.mark.asyncio
async def test_collect_packages_happy_path(fake_salt_api):
    """Two minions on different distros — collector should:

    * call pkg.list_pkgs once and grains.get once
    * tag debian minion source='apt', rhel source='rpm'
    * flatten attr=version,arch returns
    * preserve arch when present, drop it when absent
    """

    def handler(payload):
        fun = payload.get("fun")
        if fun == "pkg.list_pkgs":
            return {
                "return": [
                    {
                        "web-01": {
                            "openssh-server": [{"version": "1:8.9p1-3ubuntu0.4", "arch": "amd64"}],
                            "vim-tiny": "2:9.0.1378-2",
                        },
                        "db-01": {
                            "openssh-server": "8.0p1-19.el8_8",
                            "bash": "4.4.20-5.el8",
                        },
                    }
                ]
            }
        if fun == "grains.get":
            return {"return": [{"web-01": "Debian", "db-01": "RedHat"}]}
        return {"return": [{}]}

    fake_salt_api.run_handler = handler
    client = _make_client(fake_salt_api)
    try:
        results = await collect_packages(client)
    finally:
        await client.aclose()

    by_id = {r.minion_id: r for r in results}
    assert set(by_id) == {"web-01", "db-01"}

    web = by_id["web-01"]
    assert web.source == "apt"
    pkgs = {(p.name, p.version, p.arch) for p in web.packages}
    assert ("openssh-server", "1:8.9p1-3ubuntu0.4", "amd64") in pkgs
    assert ("vim-tiny", "2:9.0.1378-2", None) in pkgs

    db = by_id["db-01"]
    assert db.source == "rpm"
    pkgs = {(p.name, p.version, p.arch) for p in db.packages}
    assert ("openssh-server", "8.0p1-19.el8_8", None) in pkgs
    assert ("bash", "4.4.20-5.el8", None) in pkgs


@pytest.mark.asyncio
async def test_collect_packages_skips_offline_minion(fake_salt_api):
    """Salt represents offline / errored minions as a non-dict (False or an
    error string). We drop those instead of writing empty snapshots."""

    def handler(payload):
        if payload.get("fun") == "pkg.list_pkgs":
            return {
                "return": [
                    {
                        "web-01": {"vim": "2:9.0.1378-2"},
                        "offline-01": False,
                        "errored-01": "Minion did not return. [Not connected]",
                    }
                ]
            }
        if payload.get("fun") == "grains.get":
            return {"return": [{"web-01": "Debian"}]}
        return {"return": [{}]}

    fake_salt_api.run_handler = handler
    client = _make_client(fake_salt_api)
    try:
        results = await collect_packages(client)
    finally:
        await client.aclose()
    assert [r.minion_id for r in results] == ["web-01"]


@pytest.mark.asyncio
async def test_collect_packages_skips_empty_response(fake_salt_api):
    """An empty pkg.list_pkgs dict for a minion is treated as "no useful data"
    and skipped — better to keep the previous snapshot than wipe it."""

    def handler(payload):
        if payload.get("fun") == "pkg.list_pkgs":
            return {"return": [{"web-01": {"vim": "2:9.0.1378-2"}, "empty-01": {}}]}
        if payload.get("fun") == "grains.get":
            return {"return": [{"web-01": "Debian", "empty-01": "Debian"}]}
        return {"return": [{}]}

    fake_salt_api.run_handler = handler
    client = _make_client(fake_salt_api)
    try:
        results = await collect_packages(client)
    finally:
        await client.aclose()
    assert [r.minion_id for r in results] == ["web-01"]


@pytest.mark.asyncio
async def test_collect_packages_unknown_os_family_yields_none_source(fake_salt_api):
    def handler(payload):
        if payload.get("fun") == "pkg.list_pkgs":
            return {"return": [{"odd-01": {"some-pkg": "1.0"}}]}
        if payload.get("fun") == "grains.get":
            return {"return": [{"odd-01": "Gentoo"}]}
        return {"return": [{}]}

    fake_salt_api.run_handler = handler
    client = _make_client(fake_salt_api)
    try:
        results = await collect_packages(client)
    finally:
        await client.aclose()
    assert len(results) == 1
    assert results[0].source is None
    assert results[0].packages[0].name == "some-pkg"


@pytest.mark.asyncio
async def test_collect_packages_uses_attr_kwarg(fake_salt_api):
    """Regression: we must request attr=version,arch so dpkg returns per-arch
    rows. Without this kwarg Debian multi-arch minions report only one of
    their two arch slots."""
    seen_payloads: list[dict] = []

    def handler(payload):
        seen_payloads.append(payload)
        if payload.get("fun") == "pkg.list_pkgs":
            return {"return": [{"web-01": {"vim": "1.0"}}]}
        if payload.get("fun") == "grains.get":
            return {"return": [{"web-01": "Debian"}]}
        return {"return": [{}]}

    fake_salt_api.run_handler = handler
    client = _make_client(fake_salt_api)
    try:
        await collect_packages(client)
    finally:
        await client.aclose()

    pkg_call = next(p for p in seen_payloads if p.get("fun") == "pkg.list_pkgs")
    assert pkg_call.get("kwarg") == {"attr": "version,arch"}
    grains_call = next(p for p in seen_payloads if p.get("fun") == "grains.get")
    assert grains_call.get("arg") == ["os_family"]
