# backend/src/halite/minions/schemas.py
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel

MinionStatus = Literal["online", "offline", "pending", "rejected", "denied"]


class MinionSummary(BaseModel):
    id: str
    ip: str | None = None
    status: MinionStatus


class MinionListOut(BaseModel):
    total: int
    minions: list[MinionSummary]


class MinionDetail(BaseModel):
    id: str
    status: MinionStatus
    ip: str | None = None
    grains: dict[str, Any] | None = None
