# backend/src/halite/minions/schemas.py
from __future__ import annotations

from pydantic import BaseModel


class MinionSummary(BaseModel):
    id: str
    ip: str | None = None


class MinionListOut(BaseModel):
    total: int
    minions: list[MinionSummary]
