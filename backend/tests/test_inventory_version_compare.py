# backend/tests/test_inventory_version_compare.py
"""Cross-package-manager version comparison tests.

The test data is laid out as ``(a, op, b, source) -> True`` so adding a new
edge case from the field is a one-line append. ``satisfies`` is the public
entry point everywhere else uses.
"""

from __future__ import annotations

import pytest

from halite.inventory.version_compare import cmp_version, satisfies

# ---------- deb ----------

DEB_CASES = [
    # (a, op, b, expected)
    # Simple numerics
    ("1.0", "eq", "1.0", True),
    ("1.0", "lt", "1.1", True),
    ("1.10", "gt", "1.2", True),
    ("2.0", "gte", "1.99", True),
    # Epoch trumps everything
    ("1:0.1", "gt", "9.9", True),
    ("2:1.0", "gt", "1:9.9", True),
    # Revision tiebreak
    ("1.0-1", "lt", "1.0-2", True),
    ("1.0-2ubuntu1", "gt", "1.0-2", True),
    # Tilde sorts BEFORE empty — pre-releases
    ("1.0~rc1", "lt", "1.0", True),
    ("1.0~rc1", "lt", "1.0~rc2", True),
    ("1.0~~", "lt", "1.0~", True),
    ("1.0~~a", "lt", "1.0~~b", True),
    # Mixed digit/non-digit runs
    ("1.0a", "lt", "1.0b", True),
    ("1.0+deb11u1", "gt", "1.0", True),
    # Real-world openssh versions
    ("1:8.9p1-3ubuntu0.4", "gt", "1:8.9p1-3", True),
    ("1:8.2p1-4ubuntu0.9", "lt", "1:8.9p1-3", True),
    # The user's example: "openssh <= 2.1.0"
    ("2.0.0-1", "lte", "2.1.0", True),
    ("2.1.0", "lte", "2.1.0", True),
    ("2.1.1", "lte", "2.1.0", False),
    ("10.0.0", "gt", "2.1.0", True),  # the lexicographic-vs-numeric gotcha
]


@pytest.mark.parametrize("a,op,b,expected", DEB_CASES)
def test_deb_compare(a, op, b, expected):
    assert satisfies(a, op, b, source="apt") is expected


# ---------- rpm ----------

RPM_CASES = [
    ("1.0", "eq", "1.0", True),
    ("1.0", "lt", "1.1", True),
    ("1.10", "gt", "1.2", True),
    # Epoch
    ("1:0.1", "gt", "9.9", True),
    # Release tiebreak
    ("1.0-1.el8", "lt", "1.0-2.el8", True),
    ("1.0-1.fc38", "lt", "1.0-1.fc39", True),
    # Tilde marks pre-release
    ("1.0~rc1", "lt", "1.0", True),
    # Real-world bash on rhel
    ("4.4.20-4.el8", "lt", "4.4.20-5.el8", True),
    ("5.1.16-1.fc38", "gt", "5.1.16-1.fc37", True),
    # openssh on rhel
    ("8.0p1-19.el8_8", "gt", "8.0p1-13.el8", True),
    # User's lte example
    ("2.0.0-1.el8", "lte", "2.1.0", True),
    ("2.1.1-1.el8", "lte", "2.1.0", False),
    ("10.0.0-1.el8", "gt", "2.1.0", True),
]


@pytest.mark.parametrize("a,op,b,expected", RPM_CASES)
def test_rpm_compare(a, op, b, expected):
    assert satisfies(a, op, b, source="rpm") is expected


# ---------- arch / pacman ----------

ARCH_CASES = [
    ("1:8.9p1-1", "gt", "8.9p1-1", True),
    ("8.9p1-2", "gt", "8.9p1-1", True),
    ("8.9p2-1", "gt", "8.9p1-1", True),
    ("9.0p1-1", "gt", "8.9p1-2", True),
]


@pytest.mark.parametrize("a,op,b,expected", ARCH_CASES)
def test_arch_compare(a, op, b, expected):
    assert satisfies(a, op, b, source="pacman") is expected


# ---------- generic / unknown source ----------

GENERIC_CASES = [
    ("1.0", "eq", "1.0", True),
    ("1.2.3", "lt", "1.10.0", True),  # the bedrock semver gotcha
    ("2.0.0", "gt", "1.999.999", True),
    ("1.0.0", "lt", "1.0.0.1", True),
    ("1.0.0-rc1", "lt", "1.0.0", True),
    ("1.0.0-rc1", "lt", "1.0.0-rc2", True),
    ("1.0a", "lt", "1.0b", True),
    # Mixed-segment fallback
    ("1.2.3a", "lt", "1.2.3b", True),
    # Pure-alpha tail
    ("alpha", "lt", "beta", True),
    # User's example, no source known
    ("2.1.0", "lte", "2.1.0", True),
    ("2.0.0", "lte", "2.1.0", True),
    ("2.1.1", "lte", "2.1.0", False),
    ("10.0.0", "gt", "2.1.0", True),
]


@pytest.mark.parametrize("a,op,b,expected", GENERIC_CASES)
def test_generic_compare(a, op, b, expected):
    assert satisfies(a, op, b, source=None) is expected
    # An unrecognised source falls through to the generic comparator.
    assert satisfies(a, op, b, source="who-knows") is expected


# ---------- symmetry / reflexivity sanity ----------


@pytest.mark.parametrize(
    "a,b,source",
    [
        ("1:8.9p1-3ubuntu0.4", "1:8.9p1-3", "apt"),
        ("5.1.16-1.fc38", "5.1.16-1.fc37", "rpm"),
        ("2.1.0", "2.0.0", None),
        ("1.0~rc1", "1.0", "apt"),
    ],
)
def test_cmp_is_antisymmetric(a, b, source):
    """If a > b then b < a; sanity check on signs."""
    forward = cmp_version(a, b, source)
    backward = cmp_version(b, a, source)
    if forward == 0:
        assert backward == 0
    else:
        assert (forward > 0) == (backward < 0)


@pytest.mark.parametrize(
    "v,source",
    [
        ("1.0", "apt"),
        ("1:8.9p1-3", "apt"),
        ("5.1.16-1.fc38", "rpm"),
        ("2.1.0", None),
        ("1.0~rc1", "apt"),
        ("4.4.20-4.el8", "rpm"),
    ],
)
def test_cmp_is_reflexive(v, source):
    assert cmp_version(v, v, source) == 0


# ---------- satisfies covers every op ----------


def test_satisfies_handles_every_op():
    for op_, expected in [("eq", True), ("ne", False), ("lte", True), ("gte", True)]:
        assert satisfies("1.0", op_, "1.0", source=None) is expected
    for op_, expected in [("lt", True), ("lte", True), ("ne", True)]:
        assert satisfies("1.0", op_, "2.0", source=None) is expected
    for op_, expected in [("gt", True), ("gte", True), ("ne", True)]:
        assert satisfies("2.0", op_, "1.0", source=None) is expected


def test_satisfies_rejects_unknown_op():
    with pytest.raises(ValueError):
        satisfies("1.0", "approx", "1.0", source=None)  # type: ignore[arg-type]
