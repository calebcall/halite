# backend/src/halite/inventory/version_compare.py
"""Cross-package-manager version comparison.

Why this exists
---------------

We persist package versions as the raw strings the system package manager
reports (``"1:9.6p1-3ubuntu13.5"``, ``"2.3-1.fc38"``, ``"4.5.1-1-x86_64"``,
``"2.1.0"``). When the user asks "every server where openssh-server <= 2.1.0",
we cannot rely on SQL string comparison — ``"10.0.0"`` is lexicographically
less than ``"2.0.0"``.

We dispatch on the package manager:

* ``apt`` / ``dpkg`` → Debian's spec (RFC: ``deb-version(5)``): epoch, upstream
  version, debian revision. Tilde is special ("less than empty").
* ``rpm`` / ``dnf`` / ``yum`` / ``zypper`` → RPM spec: epoch, version, release.
  Numeric runs compare numerically, alpha runs compare alphabetically, ``~``
  is a pre-release marker as in deb.
* ``pacman`` → Arch's ``vercmp`` rules (close to RPM but no epoch tilde
  semantics).
* Unknown / mixed → a "generic" comparator that splits on ``.`` and ``-`` and
  compares each segment numerically when both sides are integers,
  lexicographically otherwise.

This module is intentionally **pure** (no I/O, no SQLAlchemy) — it's called
from the query handler row-by-row in Python after SQL has narrowed candidates.

A *thousand* candidates with this comparator complete in well under 100 ms.
If you ever need to do fleet-wide range scans cheaper than that, the right
move is to add a precomputed sortkey column (epoch:major:minor:... packed in
fixed-width fields) at write time and let SQL do the range. Out of scope here.
"""

from __future__ import annotations

import re
from typing import Literal

# Comparator return values follow the C ``cmp`` convention: <0, 0, >0.
Op = Literal["eq", "ne", "lt", "lte", "gt", "gte"]


# Map every source value we might see from a salt minion into one of the
# three "families" of version semantics we support. Anything we don't know
# falls back to the generic comparator.
_DEB_SOURCES = frozenset({"apt", "deb", "dpkg"})
_RPM_SOURCES = frozenset({"rpm", "dnf", "yum", "zypper"})
_ARCH_SOURCES = frozenset({"pacman", "arch"})


# ---------- public API ----------


def cmp_version(a: str, b: str, source: str | None) -> int:
    """Return <0, 0, or >0 comparing ``a`` to ``b`` under ``source``'s rules.

    Symmetric with the C ``strcmp`` convention.
    """
    source = (source or "").lower()
    if source in _DEB_SOURCES:
        return _deb_compare(a, b)
    if source in _RPM_SOURCES:
        return _rpm_compare(a, b)
    if source in _ARCH_SOURCES:
        return _rpm_compare(a, b)  # close enough; tilde behaves the same way
    return _generic_compare(a, b)


def satisfies(version: str, op: Op, target: str, source: str | None) -> bool:
    """``True`` iff ``version`` ``op`` ``target`` under ``source``'s rules."""
    c = cmp_version(version, target, source)
    if op == "eq":
        return c == 0
    if op == "ne":
        return c != 0
    if op == "lt":
        return c < 0
    if op == "lte":
        return c <= 0
    if op == "gt":
        return c > 0
    if op == "gte":
        return c >= 0
    raise ValueError(f"unknown comparison op: {op!r}")


# ---------- debian / dpkg ----------
#
# A deb version is ``[epoch:]upstream_version[-debian_revision]``.
# Comparison rules from deb-version(5):
#   1. Compare epochs numerically (default 0).
#   2. Compare upstream versions character-by-character, but pull out
#      consecutive digit runs and compare those numerically.
#   3. Compare debian revisions the same way.
#   4. Tilde sorts BEFORE everything, including "empty" — so "1.0~rc1" < "1.0".


def _deb_compare(a: str, b: str) -> int:
    ea, ua, ra = _deb_split(a)
    eb, ub, rb = _deb_split(b)
    if ea != eb:
        return -1 if ea < eb else 1
    c = _deb_compare_segment(ua, ub)
    if c != 0:
        return c
    return _deb_compare_segment(ra, rb)


def _deb_split(v: str) -> tuple[int, str, str]:
    epoch = 0
    if ":" in v:
        prefix, _, rest = v.partition(":")
        if prefix.isdigit():
            epoch = int(prefix)
            v = rest
    if "-" in v:
        upstream, _, revision = v.rpartition("-")
    else:
        upstream, revision = v, ""
    return epoch, upstream, revision


def _deb_char_order(ch: str) -> int:
    """Order used inside deb non-digit runs.

    Per deb-version(5):
      - Tilde sorts before any character, even empty string.
      - Letters sort before non-letters.
      - Otherwise the ascii code is used.
    """
    if ch == "":
        return 0
    if ch == "~":
        return -1
    if ch.isalpha():
        return ord(ch)
    # Non-letter non-digit non-tilde: push above the letter range so it sorts
    # AFTER letters. (Standard says non-alphanumerics sort later than letters.)
    return ord(ch) + 256


def _deb_compare_segment(a: str, b: str) -> int:
    """Compare a single deb sub-segment (either upstream or revision)."""
    i = j = 0
    while i < len(a) or j < len(b):
        # Non-digit run comparison, char by char.
        while (i < len(a) and not a[i].isdigit()) or (j < len(b) and not b[j].isdigit()):
            ca = a[i] if i < len(a) and not a[i].isdigit() else ""
            cb = b[j] if j < len(b) and not b[j].isdigit() else ""
            if ca == "" and cb == "":
                break
            oa = _deb_char_order(ca)
            ob = _deb_char_order(cb)
            if oa != ob:
                return -1 if oa < ob else 1
            if ca:
                i += 1
            if cb:
                j += 1
        # Digit run comparison, numerically.
        na = nb = 0
        while i < len(a) and a[i].isdigit():
            na = na * 10 + int(a[i])
            i += 1
        while j < len(b) and b[j].isdigit():
            nb = nb * 10 + int(b[j])
            j += 1
        if na != nb:
            return -1 if na < nb else 1
    return 0


# ---------- rpm ----------
#
# RPM version: ``[epoch:]version[-release]``. Comparison runs over each part
# (epoch / version / release) by:
#   * splitting on non-alphanumeric (and treating ``~`` as a "less than empty"
#     marker that introduces a sub-run)
#   * each run is either all-digits (compared numerically) or all-letters
#     (compared lexicographically)
#   * digit runs sort *above* letter runs


def _rpm_compare(a: str, b: str) -> int:
    ea, va, ra = _rpm_split(a)
    eb, vb, rb = _rpm_split(b)
    if ea != eb:
        return -1 if ea < eb else 1
    c = _rpm_compare_segment(va, vb)
    if c != 0:
        return c
    return _rpm_compare_segment(ra, rb)


def _rpm_split(v: str) -> tuple[int, str, str]:
    epoch = 0
    if ":" in v:
        prefix, _, rest = v.partition(":")
        if prefix.isdigit():
            epoch = int(prefix)
            v = rest
    if "-" in v:
        version, _, release = v.partition("-")
    else:
        version, release = v, ""
    return epoch, version, release


_RPM_TOKEN_RE = re.compile(r"(\d+|[A-Za-z]+|~)")


def _rpm_compare_segment(a: str, b: str) -> int:
    ta = _RPM_TOKEN_RE.findall(a)
    tb = _RPM_TOKEN_RE.findall(b)
    for x, y in zip(ta, tb, strict=False):
        if x == y:
            continue
        if x == "~":
            return -1
        if y == "~":
            return 1
        if x.isdigit() and y.isdigit():
            ix, iy = int(x), int(y)
            if ix != iy:
                return -1 if ix < iy else 1
        elif x.isdigit():
            return 1  # digit run > letter run
        elif y.isdigit():
            return -1
        else:
            return -1 if x < y else 1
    if len(ta) == len(tb):
        return 0
    # The side with more tokens wins, UNLESS its next token is "~".
    longer, shorter = (ta, tb) if len(ta) > len(tb) else (tb, ta)
    if longer[len(shorter)] == "~":
        return 1 if longer is tb else -1
    return 1 if longer is ta else -1


# ---------- generic (used when source is unknown) ----------


def _generic_compare(a: str, b: str) -> int:
    """Numeric-when-possible segment compare, splitting on ``.`` ``-`` ``_`` ``+``.

    Handles ``"1.2.3"`` < ``"1.10.0"`` < ``"2.0.0"`` correctly. Recognises a
    SemVer-style pre-release marker: when one side has additional tokens and
    the next of those starts with an alpha character, the longer side is
    treated as a pre-release of the shorter (i.e. ``"1.0.0-rc1"`` < ``"1.0.0"``
    < ``"1.0.0.1"``). Build metadata (``"1.0.0+sha"``) is grouped into the
    same "trailing alpha = lesser" bucket as a known limitation — callers
    that need strict SemVer should pass ``source="pip"`` (future) rather than
    ``None``.
    """
    sa = re.split(r"[.\-_+]", a)
    sb = re.split(r"[.\-_+]", b)
    for x, y in zip(sa, sb, strict=False):
        if x.isdigit() and y.isdigit():
            ix, iy = int(x), int(y)
            if ix != iy:
                return -1 if ix < iy else 1
            continue
        # Mixed token (e.g. "3a", "1rc1") — split into numeric prefix + tail.
        mx = re.match(r"^(\d*)(.*)$", x)
        my = re.match(r"^(\d*)(.*)$", y)
        assert mx is not None and my is not None
        nx = int(mx.group(1)) if mx.group(1) else 0
        ny = int(my.group(1)) if my.group(1) else 0
        if nx != ny:
            return -1 if nx < ny else 1
        tx, ty = mx.group(2), my.group(2)
        # Empty tail beats a non-empty one ("1" > "1rc1").
        if tx == "" and ty != "":
            return 1
        if ty == "" and tx != "":
            return -1
        if tx != ty:
            return -1 if tx < ty else 1
    if len(sa) == len(sb):
        return 0
    # The side with more tokens is bigger — UNLESS its first extra token starts
    # with an alpha character, in which case it's a pre-release suffix and is
    # actually smaller than the shorter side.
    if len(sa) > len(sb):
        extra = sa[len(sb)]
        if extra and extra[0].isalpha():
            return -1
        return 1
    extra = sb[len(sa)]
    if extra and extra[0].isalpha():
        return 1
    return -1
