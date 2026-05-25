# backend/tests/test_minions_service.py
"""Unit tests for the minion IP-picking heuristic.

These tests exercise ``_pick_primary_ip`` directly with realistic grain
shapes — no DB, no salt-api, no FastAPI app. They're here so the heuristic
stays honest as we extend it.
"""

from __future__ import annotations

from halite.minions.service import _pick_primary_ip


def test_pick_primary_ip_prefers_gateway_subnet_over_docker_bridges():
    """Real-world shape from a docker host: fqdn_ip4 starts with bridge IPs
    but the gateway-sharing interface is the right answer."""
    grains = {
        "fqdn_ip4": [
            "172.18.0.1",
            "172.17.0.1",
            "172.19.0.1",
            "192.69.220.226",
            "172.20.0.1",
        ],
        "ip4_gw": "192.69.220.225",
        "ip4_interfaces": {
            "lo": ["127.0.0.1"],
            "enp10s0f0np0": ["192.69.220.226"],
            "enp5s0": [],
            "docker0": ["172.17.0.1"],
            "br-e1278ea2f7a6": ["172.18.0.1"],
            "br-69862f1fc6ea": ["172.19.0.1"],
            "br-04e7c2495b0e": ["172.20.0.1"],
        },
    }
    assert _pick_primary_ip(grains, fallback="172.18.0.1") == "192.69.220.226"


def test_pick_primary_ip_simple_lan_host():
    """A normal LAN host: one real interface, gateway on the same /24."""
    grains = {
        "fqdn_ip4": ["10.0.0.42"],
        "ip4_gw": "10.0.0.1",
        "ip4_interfaces": {
            "lo": ["127.0.0.1"],
            "eth0": ["10.0.0.42"],
        },
    }
    assert _pick_primary_ip(grains, fallback="10.0.0.42") == "10.0.0.42"


def test_pick_primary_ip_no_gateway_falls_back_to_first_real_iface():
    grains = {
        "fqdn_ip4": [],
        "ip4_interfaces": {
            "lo": ["127.0.0.1"],
            "eth0": ["10.20.30.40"],
            "docker0": ["172.17.0.1"],
        },
    }
    assert _pick_primary_ip(grains, fallback="172.17.0.1") == "10.20.30.40"


def test_pick_primary_ip_only_virtual_ifaces_falls_back_to_fqdn():
    """Pathological: every iface in ip4_interfaces is virtual. We still try
    fqdn_ip4 before giving up to the fallback."""
    grains = {
        "fqdn_ip4": ["203.0.113.5"],
        "ip4_gw": "203.0.113.1",
        "ip4_interfaces": {
            "lo": ["127.0.0.1"],
            "docker0": ["172.17.0.1"],
        },
    }
    assert _pick_primary_ip(grains, fallback="172.17.0.1") == "203.0.113.5"


def test_pick_primary_ip_empty_grains_returns_fallback():
    assert _pick_primary_ip({}, fallback="10.0.0.5") == "10.0.0.5"
    assert _pick_primary_ip(None, fallback="10.0.0.5") == "10.0.0.5"
    assert _pick_primary_ip(None, fallback=None) is None


def test_pick_primary_ip_gateway_match_requires_at_least_two_octets():
    """If nothing matches the gateway closely, don't accept a single-octet
    match — fall through to the first-real-iface heuristic instead."""
    grains = {
        "fqdn_ip4": [],
        "ip4_gw": "203.0.113.1",
        "ip4_interfaces": {
            "lo": ["127.0.0.1"],
            "eth0": ["203.99.99.99"],  # only shares one octet with 203.0.113.x
            "eth1": ["198.51.100.7"],
        },
    }
    # Single-octet match is too weak; we fall back to "first usable on a real
    # iface" which is eth0's address (dict insertion order).
    assert _pick_primary_ip(grains, fallback=None) == "203.99.99.99"


def test_pick_primary_ip_skips_ipv6_in_ip4_interfaces():
    """Salt sometimes mixes link-local IPv6 into ip4_interfaces values; we
    must ignore those when scoring against the IPv4 gateway."""
    grains = {
        "ip4_gw": "10.0.0.1",
        "ip4_interfaces": {
            "lo": ["127.0.0.1", "::1"],
            "eth0": ["10.0.0.42", "fe80::1"],
        },
    }
    assert _pick_primary_ip(grains, fallback=None) == "10.0.0.42"
