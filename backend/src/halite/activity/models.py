from __future__ import annotations

from datetime import datetime
from typing import Any

import sqlalchemy as sa
from sqlalchemy import JSON, BigInteger, Boolean, DateTime, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from halite.db import Base

# SQLite-friendly BIGINT autoincrement (same pattern as audit_log).
_pk_type = BigInteger().with_variant(Integer(), "sqlite")


class ActivityEvent(Base):
    """Durable append-only log of fleet events: jobs, key activity, and minion
    presence.  Deliberately has no foreign key to the job or minion tables —
    it is an independent event log that remains intact even when minions come
    and go from the master's key list (same rationale as inventory/models.py).
    """

    __tablename__ = "activity_events"
    __table_args__ = (
        sa.Index("ix_activity_events_ts", "ts"),
        sa.Index("ix_activity_events_category_ts", "category", "ts"),
        sa.Index("ix_activity_events_minion_ts", "minion_id", "ts"),
        sa.Index("ix_activity_events_jid", "jid"),
    )

    id: Mapped[int] = mapped_column(_pk_type, primary_key=True, autoincrement=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    category: Mapped[str] = mapped_column(String(32), nullable=False)
    event_type: Mapped[str] = mapped_column(String(32), nullable=False)
    minion_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    jid: Mapped[str | None] = mapped_column(String(64), nullable=True)
    fun: Mapped[str | None] = mapped_column(String(128), nullable=True)
    success: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    changed: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    initiator: Mapped[str | None] = mapped_column(String(255), nullable=True)
    target: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    summary: Mapped[str] = mapped_column(String(512), nullable=False)
    raw: Mapped[dict[str, Any] | None] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"), nullable=True
    )
