from __future__ import annotations

import re
from typing import Any, TypedDict

_JOB_RE = re.compile(r"^salt/job/(?P<jid>\d{20})/(?P<kind>new|ret)(?:/(?P<minion>.+))?$")
_MINION_START_RE = re.compile(r"^salt/minion/(?P<minion>.+)/start$")


def _opt_str(v: object) -> str | None:
    """Coerce v to a non-empty string, or None.

    Guards the String(2048) DB column from receiving non-string values such as
    a list (e.g. ``tgt=["web01","web02"]`` from ``salt -L`` list targeting).
    """
    if v is None:
        return None
    s = str(v)
    return s or None
# Map of Salt key/auth "act" values to our event_type suffix.
_KEY_ACTS = {"accept": "accept", "reject": "reject", "delete": "delete", "pend": "pend"}


class NormalizedEvent(TypedDict):
    category: str
    event_type: str
    minion_id: str | None
    jid: str | None
    fun: str | None
    success: bool | None
    changed: bool | None
    initiator: str | None
    target: str | None
    duration_ms: int | None
    summary: str
    raw: dict[str, Any]


def _ret_made_changes(data: dict[str, Any]) -> bool | None:
    """Whether a job return made changes.

    A Salt state return (``data["return"]``) is a dict keyed by state-id, each
    value a dict with a ``"changes"`` key. Returns True if any state value has a
    non-empty changes dict, False if it's a state-style dict with no changes, and
    None when ``return`` isn't a dict (e.g. test.ping's True, cmd.run's string)
    so "changed" simply doesn't apply.
    """
    ret = data.get("return")
    if not isinstance(ret, dict):
        return None
    return any(isinstance(v, dict) and v.get("changes") for v in ret.values())


def _ret_duration_ms(data: dict[str, Any]) -> int | None:
    """Total wall-clock duration of a state return, in milliseconds.

    A Salt state return (``data["return"]``) is a dict keyed by state-id, each
    value a dict that may carry a numeric ``"duration"`` (milliseconds, float).
    Sum those values across states and return the rounded int. Returns None when
    ``return`` isn't a state-style dict (e.g. test.ping's True, cmd.run's string)
    or when no numeric durations are present — we never fabricate a value.
    """
    ret = data.get("return")
    if not isinstance(ret, dict):
        return None
    total = 0.0
    found = False
    for v in ret.values():
        if isinstance(v, dict):
            d = v.get("duration")
            if isinstance(d, int | float) and not isinstance(d, bool):
                total += float(d)
                found = True
    return int(round(total)) if found else None


def normalize_event(tag: str, data: dict[str, Any]) -> NormalizedEvent | None:
    """Normalize a raw Salt event into a typed dict, or None to drop it.

    v1 surfaces three families: jobs (new/ret), minion presence (start),
    and key activity (salt/key + salt/auth). Everything else is dropped.
    """
    raw = {"tag": tag, "data": data}

    m = _JOB_RE.match(tag)
    if m:
        jid = m.group("jid")
        fun = data.get("fun")
        if m.group("kind") == "new":
            return NormalizedEvent(
                category="job", event_type="job.new", minion_id=None, jid=jid,
                fun=fun, success=None, changed=None,
                initiator=_opt_str(data.get("user")), target=_opt_str(data.get("tgt")), duration_ms=None,
                summary=f"{fun or 'job'} dispatched ({len(data.get('minions') or [])} minions)",
                raw=raw,
            )
        minion = m.group("minion") or data.get("id")
        retcode = data.get("retcode")
        success = (retcode == 0) if retcode is not None else None
        return NormalizedEvent(
            category="job", event_type="job.ret", minion_id=minion, jid=jid,
            fun=fun, success=success, changed=_ret_made_changes(data),
            initiator=_opt_str(data.get("user")), target=_opt_str(data.get("tgt")),
            duration_ms=_ret_duration_ms(data),
            summary=f"{minion} returned {fun or 'job'}"
            + ("" if success is None else (" ✓" if success else " ✗")),
            raw=raw,
        )

    m = _MINION_START_RE.match(tag)
    if m:
        minion = m.group("minion")
        return NormalizedEvent(
            category="minion", event_type="minion.start", minion_id=minion, jid=None,
            fun=None, success=None, changed=None,
            initiator=None, target=None, duration_ms=None,
            summary=f"{minion} came online", raw=raw,
        )

    if tag == "salt/key" or tag == "salt/auth":
        act = str(data.get("act", "")).lower()
        suffix = _KEY_ACTS.get(act)
        if suffix is None:
            return None
        minion = data.get("id")
        labels = {
            "accept": "accepted", "reject": "rejected",
            "delete": "deleted", "pend": "pending",
        }
        return NormalizedEvent(
            category="key", event_type=f"key.{suffix}", minion_id=minion, jid=None,
            fun=None, success=None, changed=None,
            initiator=None, target=None, duration_ms=None,
            summary=f"{minion} key {labels[suffix]}", raw=raw,
        )

    return None
