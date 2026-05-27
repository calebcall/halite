from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

# Anchored regex matching salt's low-state key format "module_|-state_id_|-name_|-fun".
# DOTALL because cmd.run state names commonly contain multi-line shell scripts.
_LOWSTATE_KEY = re.compile(
    r"^([a-z_]+)_\|-(.*?)_\|-(.*?)_\|-([a-z_]+)$",
    re.DOTALL,
)


@dataclass(frozen=True)
class HighstateCounts:
    total: int
    passed: int
    failed: int
    changed: int
    duration_ms: int


def _has_changes(changes: Any) -> bool:
    if not changes:
        return False
    if isinstance(changes, dict):
        return len(changes) > 0
    if isinstance(changes, list):
        return len(changes) > 0
    return False


def summarize_lowstate(value: Any) -> HighstateCounts | None:
    """Return counts for a salt low-state result dict, or None if the value
    doesn't look like a parseable highstate return."""
    if not isinstance(value, dict) or not value:
        return None

    total = 0
    passed = 0
    failed = 0
    changed = 0
    duration_ms = 0
    for key, state in value.items():
        if not _LOWSTATE_KEY.match(key):
            return None
        if not isinstance(state, dict):
            return None
        if "result" not in state or "comment" not in state:
            return None
        total += 1
        if state["result"] is True:
            passed += 1
        elif state["result"] is False:
            failed += 1
        if _has_changes(state.get("changes")):
            changed += 1
        dur = state.get("duration")
        if isinstance(dur, int | float):
            duration_ms += int(dur)
    return HighstateCounts(
        total=total,
        passed=passed,
        failed=failed,
        changed=changed,
        duration_ms=duration_ms,
    )
