from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Query
from sqlalchemy import func, select

from halite.audit.models import AuditEntry
from halite.audit.schemas import AuditEntryOut, AuditListOut
from halite.db import SessionDep
from halite.deps import require_perm

router = APIRouter(prefix="/api/audit", tags=["audit"])


@router.get("", response_model=AuditListOut, dependencies=[require_perm("view", "audit:*")])
async def list_audit(
    db: SessionDep,
    user_id: Annotated[uuid.UUID | None, Query()] = None,
    action: Annotated[str | None, Query()] = None,
    decision: Annotated[str | None, Query()] = None,
    since: Annotated[datetime | None, Query()] = None,
    until: Annotated[datetime | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> AuditListOut:
    stmt = select(AuditEntry)
    count_stmt = select(func.count()).select_from(AuditEntry)

    if user_id is not None:
        stmt = stmt.where(AuditEntry.user_id == user_id)
        count_stmt = count_stmt.where(AuditEntry.user_id == user_id)
    if action is not None:
        stmt = stmt.where(AuditEntry.action == action)
        count_stmt = count_stmt.where(AuditEntry.action == action)
    if decision is not None:
        stmt = stmt.where(AuditEntry.decision == decision)
        count_stmt = count_stmt.where(AuditEntry.decision == decision)
    if since is not None:
        stmt = stmt.where(AuditEntry.at >= since)
        count_stmt = count_stmt.where(AuditEntry.at >= since)
    if until is not None:
        stmt = stmt.where(AuditEntry.at < until)
        count_stmt = count_stmt.where(AuditEntry.at < until)

    stmt = stmt.order_by(AuditEntry.at.desc()).limit(limit).offset(offset)

    total = (await db.execute(count_stmt)).scalar_one()
    rows = (await db.execute(stmt)).scalars().all()
    entries = [AuditEntryOut.model_validate(r, from_attributes=True) for r in rows]
    return AuditListOut(total=total, entries=entries)
