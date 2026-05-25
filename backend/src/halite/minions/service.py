# backend/src/halite/minions/service.py
from __future__ import annotations

from typing import Any

from halite.minions.schemas import MinionDetail, MinionStatus, MinionSummary
from halite.salt.client import SaltAPIClient

_STATE_TO_STATUS: dict[str, MinionStatus] = {
    "minions_pre": "pending",
    "minions_rejected": "rejected",
    "minions_denied": "denied",
}

# Interface-name prefixes that are typically *not* the box's primary network
# attachment: docker bridges, libvirt/qemu bridges, vmware/virtualbox bridges,
# veth pairs, custom bridges, tun/tap, wireguard, etc. Real interface names
# (en*, eth*, wl*, enp*, eno*, wlp*) don't match these and so survive the
# filter. We intentionally do *not* filter wireguard / tailscale, because on
# some hosts those legitimately are the primary IP path.
_VIRTUAL_IFACE_PREFIXES: tuple[str, ...] = (
    "docker",
    "br-",
    "veth",
    "virbr",
    "vmnet",
    "vboxnet",
    "vnet",
    "tap",
    "lo",
)


def _is_virtual_iface(name: str) -> bool:
    if not name or name == "lo":
        return True
    return name.startswith(_VIRTUAL_IFACE_PREFIXES)


def _is_unwanted_ip(ip: str) -> bool:
    """Loopback / link-local / empty addresses we never want to display."""
    if not ip:
        return True
    if ip.startswith("127."):
        return True
    if ip.startswith("169.254."):
        return True
    return False


def _prefix_octet_match(a: str, b: str) -> int:
    """How many leading dotted-decimal octets two IPv4 strings have in common."""
    score = 0
    for x, y in zip(a.split("."), b.split("."), strict=False):
        if x == y:
            score += 1
        else:
            break
    return score


def _pick_primary_ip(grains: dict[str, Any] | None, fallback: str | None = None) -> str | None:
    """Pick the IP that best represents this minion's primary network address.

    Heuristic (in order):

    1. If ``ip4_gw`` is known and ``ip4_interfaces`` is present, pick the IP
       from a non-virtual interface that shares the most leading octets with
       the gateway address (at least the first two, i.e. a /16-or-better
       match). On servers running docker, this reliably picks the real
       interface's IP rather than the ``172.x.x.x`` docker bridge addresses,
       because the gateway is on the real network and the bridges aren't.

    2. Otherwise, pick the first non-loopback / non-link-local IP from a
       non-virtual interface in ``ip4_interfaces``.

    3. Otherwise, pick the first usable IP from ``fqdn_ip4``.

    4. Otherwise, return ``fallback`` (typically the IP that ``manage.present``
       surfaced from the minion's ``ipv4`` grain).
    """
    if not isinstance(grains, dict):
        return fallback

    iface_map = grains.get("ip4_interfaces") if isinstance(grains, dict) else None
    gateway = grains.get("ip4_gw") if isinstance(grains, dict) else None

    # Step 1: gateway-based pick.
    if isinstance(gateway, str) and gateway and isinstance(iface_map, dict):
        best_ip: str | None = None
        best_score = -1
        for iface, ips in iface_map.items():
            if not isinstance(ips, list) or _is_virtual_iface(str(iface)):
                continue
            for ip in ips:
                if not isinstance(ip, str) or _is_unwanted_ip(ip):
                    continue
                if ":" in ip:  # skip IPv6 entries mixed into ip4_interfaces
                    continue
                score = _prefix_octet_match(gateway, ip)
                if score > best_score:
                    best_score = score
                    best_ip = ip
        if best_ip is not None and best_score >= 2:
            return best_ip

    # Step 2: first usable IP from any non-virtual interface.
    if isinstance(iface_map, dict):
        for iface, ips in iface_map.items():
            if not isinstance(ips, list) or _is_virtual_iface(str(iface)):
                continue
            for ip in ips:
                if isinstance(ip, str) and not _is_unwanted_ip(ip) and ":" not in ip:
                    return ip

    # Step 3: fqdn_ip4 (best-effort — may be polluted by docker bridges).
    fqdn = grains.get("fqdn_ip4") if isinstance(grains, dict) else None
    if isinstance(fqdn, list):
        for entry in fqdn:
            if isinstance(entry, str) and not _is_unwanted_ip(entry):
                return entry
    elif isinstance(fqdn, str) and fqdn:
        return fqdn

    # Step 4: fallback.
    return fallback


async def list_minions_with_status(client: SaltAPIClient) -> list[MinionSummary]:
    """Compose connected + key-state to produce a unified list.

    For online minions we do a single batched grain fetch (``fqdn_ip4``,
    ``ip4_gw``, ``ip4_interfaces``) and run them through ``_pick_primary_ip``
    so each row shows the real primary IP — not the first ``172.x.x.x`` docker
    bridge that happened to be at the top of the ``ipv4`` grain.
    """
    connected = await client.list_connected_minions()
    keys = await client.list_minion_keys()

    network_grains: dict[str, dict[str, Any]] = {}
    if connected:
        target_list = ",".join(connected.keys())
        try:
            network_grains = await client.get_network_grains_map(target_list, target_type="list")
        except Exception:
            # Non-fatal: fall back to whatever IP manage.present returned.
            network_grains = {}

    out: list[MinionSummary] = []
    accepted = keys.get("minions", [])
    for mid in accepted:
        if mid in connected:
            ip = _pick_primary_ip(network_grains.get(mid), connected.get(mid)) or None
            out.append(MinionSummary(id=mid, ip=ip, status="online"))
        else:
            out.append(MinionSummary(id=mid, ip=None, status="offline"))

    for bucket, status in _STATE_TO_STATUS.items():
        for mid in keys.get(bucket, []):
            out.append(MinionSummary(id=mid, ip=None, status=status))

    out.sort(key=lambda m: m.id)
    return out


async def get_minion_detail(client: SaltAPIClient, minion_id: str) -> MinionDetail | None:
    """Returns full detail for a minion, or None if the minion isn't known."""
    connected = await client.list_connected_minions()
    keys = await client.list_minion_keys()

    if minion_id in keys.get("minions", []):
        if minion_id in connected:
            grains = await client.get_minion_grains(minion_id)
            ip = _pick_primary_ip(grains, connected.get(minion_id))
            return MinionDetail(id=minion_id, status="online", ip=ip, grains=grains)
        return MinionDetail(id=minion_id, status="offline", ip=None, grains=None)

    for bucket, status in _STATE_TO_STATUS.items():
        if minion_id in keys.get(bucket, []):
            return MinionDetail(id=minion_id, status=status, ip=None, grains=None)

    return None
