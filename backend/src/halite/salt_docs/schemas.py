# backend/src/halite/salt_docs/schemas.py
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class SaltFunctionsOut(BaseModel):
    functions: list[str]
    cached_at: datetime
