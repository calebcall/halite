# backend/src/halite/minions/schemas.py
from __future__ import annotations

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
