# backend/src/halite/jobs/schemas.py
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

JobStatus = Literal["running", "complete"]


class JobSummary(BaseModel):
    jid: str
    function: str
    target: str
    target_type: str | None = None
    user: str | None = None
    start_time: str | None = None
    status: JobStatus = "complete"


class JobsListOut(BaseModel):
    # total is the size of the returned `jobs` list — i.e. post-slice, not
    # the size of the master's full job cache. If we ever introduce
    # server-side pagination this should be revisited so callers can tell
    # how many records exist past `limit`.
    total: int
    jobs: list[JobSummary]
    last_polled_at: datetime | None = None
    active_known: bool = False


class JobMinionResult(BaseModel):
    minion: str
    success: bool | None = None
    retcode: int | None = None
    return_value: Any = None


class JobDetail(BaseModel):
    jid: str
    function: str
    arguments: list[Any] = []
    # additionalProperties=True so openapi-typescript emits the kwargs
    # type as { [key: string]: unknown } instead of Record<string, never>.
    kwargs: dict[str, Any] = Field(default_factory=dict, json_schema_extra={"additionalProperties": True})
    target: str
    target_type: str | None = None
    user: str | None = None
    start_time: str | None = None
    minions: list[str] = []
    results: list[JobMinionResult] = []


class JobActivityBucket(BaseModel):
    # ISO-8601 UTC, e.g. "2026-05-25T10:00:00Z" — the start of the bucket's hour.
    hour_start: str
    count: int


class JobActivityOut(BaseModel):
    # Width of the rolling window the buckets span, in hours.
    hours: int
    # Always exactly `hours` entries, oldest first, in chronological order.
    buckets: list[JobActivityBucket]
    # Sum of bucket counts — total jobs dispatched in the window.
    total: int
    # Jobs currently executing, regardless of when they started (some may
    # predate the window).
    running: int
    last_polled_at: datetime | None = None
    active_known: bool = False
