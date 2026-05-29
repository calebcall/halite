from __future__ import annotations

import re
from typing import Any, TypedDict

_JOB_RE = re.compile(r"^salt/job/(?P<jid>\d{20})/(?P<kind>new|ret)(?:/(?P<minion>.+))?$")
_MINION_START_RE = re.compile(r"^salt/minion/(?P<minion>.+)/start$")
# Map of Salt key/auth "act" values to our event_type suffix.
_KEY_ACTS = {"accept": "accept", "reject": "reject", "delete": "delete", "pend": "pend"}


class NormalizedEvent(TypedDict):
    category: str
    event_type: str
    minion_id: str | None
    jid: str | None
    fun: str | None
    success: bool | None
    summary: str
    raw: dict[str, Any]


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
                fun=fun, success=None,
                summary=f"{fun or 'job'} dispatched ({len(data.get('minions') or [])} minions)",
                raw=raw,
            )
        minion = m.group("minion") or data.get("id")
        retcode = data.get("retcode")
        success = (retcode == 0) if retcode is not None else None
        return NormalizedEvent(
            category="job", event_type="job.ret", minion_id=minion, jid=jid,
            fun=fun, success=success,
            summary=f"{minion} returned {fun or 'job'}"
            + ("" if success is None else (" ✓" if success else " ✗")),
            raw=raw,
        )

    m = _MINION_START_RE.match(tag)
    if m:
        minion = m.group("minion")
        return NormalizedEvent(
            category="minion", event_type="minion.start", minion_id=minion, jid=None,
            fun=None, success=None, summary=f"{minion} came online", raw=raw,
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
            fun=None, success=None, summary=f"{minion} key {labels[suffix]}", raw=raw,
        )

    return None
