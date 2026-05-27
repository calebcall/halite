# backend/src/halite/inventory/collectors.py
"""Pure async functions that pull inventory data from salt-api.

Each collector is responsible for *one* facet (packages, services, ...) and
returns a uniform ``CollectorResult`` shape so the persistence layer
(``halite.inventory.service``) doesn't have to know which facet it's writing.

Design rules these collectors all follow:

* **No DB access.** They take a ``SaltAPIClient`` and return data objects.
* **Defensive parsing.** Salt's return shape varies subtly across module
  versions (e.g. ``pkg.list_pkgs`` returns ``{name: str}`` by default and
  ``{name: [{"version": v, "arch": a}]}`` with ``attr=version,arch``). The
  collector normalises into a list of typed tuples that the model layer can
  consume without further unpacking.
* **Quiet on offline minions.** If a minion doesn't respond to ``test.ping``
  in salt's window, it's simply absent from the result map. We drop it; the
  scheduler will pick it up next time around. The DB keeps that minion's
  previous snapshot.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from halite.salt.client import SaltAPIClient

# os_family grain -> the value we store in inventory_package.source. The
# string ends up driving the version-comparison dispatcher in
# ``halite.inventory.version_compare`` so it MUST line up with the keys
# recognised there.
_OS_FAMILY_TO_SOURCE: dict[str, str] = {
    "Debian": "apt",
    "RedHat": "rpm",
    "Rocky": "rpm",
    "AlmaLinux": "rpm",
    "Suse": "rpm",
    "SUSE": "rpm",
    "openSUSE": "rpm",
    "Arch": "pacman",
}


def _classify_source(os_family: str | None) -> str | None:
    if not os_family:
        return None
    return _OS_FAMILY_TO_SOURCE.get(os_family)


@dataclass(slots=True)
class PackageEntry:
    """One installed package on one minion."""

    name: str
    version: str
    arch: str | None = None


@dataclass(slots=True)
class CollectorResult:
    """All packages a single minion is currently reporting, plus metadata."""

    minion_id: str
    packages: list[PackageEntry] = field(default_factory=list)
    source: str | None = None  # 'apt' | 'rpm' | 'pacman' | None
    collected_at: datetime = field(default_factory=lambda: datetime.now(tz=UTC))
    salt_jid: str | None = None


def _flatten_pkg_value(value: Any) -> list[tuple[str, str | None]]:
    """Turn the value-side of one entry in ``pkg.list_pkgs`` into ``[(version, arch), ...]``.

    Handles three real-world shapes:

      * ``"1.2.3-1ubuntu1"``                                     (plain scalar)
      * ``["1.2.3-1ubuntu1", "1.2.3-2ubuntu1"]``                 (versions_as_list)
      * ``[{"version": "1.2.3-1ubuntu1", "arch": "amd64"}, ...]`` (attr=version,arch)

    Empty / malformed entries are dropped.
    """
    out: list[tuple[str, str | None]] = []
    if isinstance(value, str):
        if value:
            out.append((value, None))
    elif isinstance(value, list):
        for entry in value:
            if isinstance(entry, dict):
                v = entry.get("version")
                a = entry.get("arch")
                if isinstance(v, str) and v:
                    out.append((v, str(a) if isinstance(a, str) and a else None))
            elif isinstance(entry, str) and entry:
                out.append((entry, None))
    return out


def _flatten_pkg_result(pkg_result: Any) -> list[PackageEntry]:
    """Flatten one minion's ``pkg.list_pkgs`` return into ``[PackageEntry, ...]``."""
    out: list[PackageEntry] = []
    if not isinstance(pkg_result, dict):
        return out
    for name, value in pkg_result.items():
        if not isinstance(name, str) or not name:
            continue
        for version, arch in _flatten_pkg_value(value):
            out.append(PackageEntry(name=name, version=version, arch=arch))
    return out


async def collect_packages(
    client: SaltAPIClient,
    *,
    target: str = "*",
    target_type: str = "glob",
) -> list[CollectorResult]:
    """Fetch ``pkg.list_pkgs`` (with ``attr=version,arch``) and ``os_family`` for
    each targeted minion. Returns one ``CollectorResult`` per minion that
    responded; offline minions are silently omitted.

    The two salt calls are fired in parallel — they're independent and the
    fan-out savings are meaningful on large fleets.

    When the caller asks for the whole fleet (``target="*"`` + glob), we
    intersect with ``manage.present`` first. Offline minions can't respond
    to ``pkg.list_pkgs`` anyway, and waiting on their salt-side timeouts
    gates the entire fan-out (with 60+ offline minions that's enough to
    blow httpx's read timeout). Explicit non-glob targets are passed
    through unchanged — caller is presumably targeting on purpose.
    """
    if target == "*" and target_type == "glob":
        try:
            present = await client.list_present_minion_ids()
        except Exception:
            present = set()
        if not present:
            return []
        target = ",".join(sorted(present))
        target_type = "list"

    pkgs_call, family_call = await asyncio.gather(
        client.local_call(
            target,
            "pkg.list_pkgs",
            target_type=target_type,
            kwarg={"attr": "version,arch"},
        ),
        client.local_call(
            target,
            "grains.get",
            target_type=target_type,
            arg=["os_family"],
        ),
    )

    collected_at = datetime.now(tz=UTC)
    out: list[CollectorResult] = []
    if not isinstance(pkgs_call, dict):
        return out
    family_map: dict[str, str] = {}
    if isinstance(family_call, dict):
        for mid, fam in family_call.items():
            if isinstance(mid, str) and isinstance(fam, str) and fam:
                family_map[mid] = fam

    for mid, pkg_data in pkgs_call.items():
        if not isinstance(mid, str):
            continue
        # Salt sometimes signals "no response" with False or an error string
        # instead of a dict. Filter those out here so the caller doesn't have
        # to think about it.
        if not isinstance(pkg_data, dict):
            continue
        packages = _flatten_pkg_result(pkg_data)
        if not packages:
            # Empty / weird response — skip rather than wipe the DB for this
            # minion. The scheduler will retry.
            continue
        out.append(
            CollectorResult(
                minion_id=mid,
                packages=packages,
                source=_classify_source(family_map.get(mid)),
                collected_at=collected_at,
            )
        )
    return out
