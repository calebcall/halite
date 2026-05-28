# backend/src/halite/minions/schemas.py
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel

MinionStatus = Literal["online", "offline", "pending", "rejected", "denied"]


class MinionSummary(BaseModel):
    id: str
    ip: str | None = None
    status: MinionStatus
    os: str | None = None
    os_family: str | None = None
    osrelease: str | None = None
    saltversion: str | None = None


class MinionListOut(BaseModel):
    total: int
    minions: list[MinionSummary]
    last_refreshed_at: datetime | None = None
    is_stale: bool = False


class MinionDetail(BaseModel):
    id: str
    status: MinionStatus
    ip: str | None = None
    grains: dict[str, Any] | None = None
    last_refreshed_at: datetime | None = None
    is_stale: bool = False


RunStatus = Literal["healthy", "changed", "unhealthy", "blocked"]


class MinionRunSummary(BaseModel):
    """One row in the per-minion recent-runs table."""

    id: uuid.UUID
    jid: str
    fun: str
    completed_at: datetime
    pass_count: int
    fail_count: int
    change_count: int
    total_count: int
    duration_ms: int
    blocked: bool
    status: RunStatus


class MinionRunsOut(BaseModel):
    minion_id: str
    total: int
    runs: list[MinionRunSummary]


class MinionComplianceBucket(BaseModel):
    completed_at: datetime
    jid: str
    pass_count: int
    fail_count: int
    change_count: int
    total_count: int
    status: RunStatus


class MinionComplianceOut(BaseModel):
    minion_id: str
    buckets: list[MinionComplianceBucket]
