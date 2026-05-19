from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel


class AuditEntryOut(BaseModel):
    id: int
    at: datetime
    user_id: uuid.UUID | None
    action: str
    resource: str
    args_json: dict[str, Any] | None
    salt_jid: str | None
    decision: str
    result_code: int
    duration_ms: int


class AuditListOut(BaseModel):
    total: int
    entries: list[AuditEntryOut]
