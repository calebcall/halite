from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class ActivityEventOut(BaseModel):
    id: int
    ts: datetime
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


class ActivityListOut(BaseModel):
    total: int
    events: list[ActivityEventOut]
