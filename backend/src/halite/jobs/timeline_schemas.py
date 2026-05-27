from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel

# state | cmd | pkg | service | test | runner | wheel | manage | other
TimelineCategory = Literal[
    "state", "cmd", "pkg", "service", "test",
    "runner", "wheel", "manage", "other",
]
# pass = state-success / non-state complete; changed = state with changes;
# failed = state with failures; running = in active_jids; unknown = no data
TimelineBarStatus = Literal["pass", "changed", "failed", "running", "unknown"]
TimelineGroupBy = Literal["function", "user"]
TimelineWindow = Literal["1h", "4h", "24h", "7d"]


class TimelineBar(BaseModel):
    """One job invocation on the timeline."""

    jid: str
    function: str
    target: str | None
    user: str | None
    started_at: datetime
    # For state.* jobs we derive completion from the max highstate_runs
    # completed_at for that jid. For non-state jobs, completion is implied
    # (jid not in active_jids) but exact end-time is unknown — completed_at
    # is None in that case and the UI renders a short marker rather than a
    # bar with width.
    completed_at: datetime | None
    status: TimelineBarStatus
    category: TimelineCategory
    # For state.* jobs only: number of minions that responded
    minion_count: int | None
    # For state.* with failures: count of failed minions (drives red intensity)
    failed_minion_count: int | None


class TimelineGroup(BaseModel):
    """A row on the timeline. ``key`` identifies the group (function name
    or username), ``label`` is what the UI displays."""

    key: str
    label: str
    category: TimelineCategory  # used to color the row label
    bar_count: int
    bars: list[TimelineBar]


class TimelineOut(BaseModel):
    window_start: datetime
    window_end: datetime
    group_by: TimelineGroupBy
    groups: list[TimelineGroup]
    total_bars: int
    last_polled_at: datetime | None  # echoes the runtime cache freshness
    active_known: bool
