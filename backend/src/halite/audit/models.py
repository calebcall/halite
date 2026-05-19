from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, BigInteger, DateTime, Integer, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from halite.db import Base

# SQLite only auto-increments INTEGER PRIMARY KEY (not BIGINT). Use a dialect
# variant so we get a real BIGINT on Postgres and INTEGER on SQLite, both
# autoincrementing.
_audit_pk_type = BigInteger().with_variant(Integer(), "sqlite")


class AuditEntry(Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(_audit_pk_type, primary_key=True, autoincrement=True)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True, index=True)
    action: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    resource: Mapped[str] = mapped_column(String(255), nullable=False)
    args_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    salt_jid: Mapped[str | None] = mapped_column(String(64), nullable=True)
    decision: Mapped[str] = mapped_column(String(16), nullable=False)
    result_code: Mapped[int] = mapped_column(Integer, nullable=False)
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
