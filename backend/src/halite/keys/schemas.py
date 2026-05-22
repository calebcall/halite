# backend/src/halite/keys/schemas.py
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

KeyStatus = Literal["accepted", "pending", "rejected", "denied"]


class KeyEntry(BaseModel):
    id: str
    status: KeyStatus


class KeysListOut(BaseModel):
    total: int
    keys: list[KeyEntry]
