from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

HealthStatus = Literal["pass", "changed", "fail", "blocked", "stale", "unknown"]


class MinionHealthOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    minion_id: str
    run_id: uuid.UUID | None
    jid: str | None
    completed_at: datetime | None
    status: HealthStatus
    pass_count: int
    fail_count: int
    change_count: int
    total_count: int
    duration_ms: int


class FleetHealthOut(BaseModel):
    total_minions: int
    minions: list[MinionHealthOut]


class ComplianceBucketOut(BaseModel):
    bucketed_at: datetime
    pass_count: int
    fail_count: int
    change_count: int
    blocked_count: int


class ComplianceSeriesOut(BaseModel):
    buckets: list[ComplianceBucketOut]


class TopFailureOut(BaseModel):
    state_id: str
    name: str
    fun: str
    failure_count: int


class TopFailuresOut(BaseModel):
    failures: list[TopFailureOut]


class RunDetailOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    minion_id: str
    jid: str
    fun: str
    completed_at: datetime
    pass_count: int
    fail_count: int
    change_count: int
    total_count: int
    duration_ms: int
    blocked: bool
    raw_result: dict[str, Any]
