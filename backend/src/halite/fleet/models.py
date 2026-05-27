from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

import sqlalchemy as sa
from sqlalchemy import JSON, DateTime, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from halite.db import Base


class HighstateRun(Base):
    __tablename__ = "highstate_runs"
    __table_args__ = (
        sa.UniqueConstraint("minion_id", "jid", name="uq_highstate_runs_minion_jid"),
        sa.Index("ix_highstate_runs_completed_at", "completed_at"),
        sa.Index("ix_highstate_runs_minion_completed", "minion_id", "completed_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    minion_id: Mapped[str] = mapped_column(String(255), nullable=False)
    jid: Mapped[str] = mapped_column(String(64), nullable=False)
    fun: Mapped[str] = mapped_column(String(64), nullable=False)
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    pass_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    fail_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    change_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    blocked: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, default=False)
    raw_result: Mapped[dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"), nullable=False
    )
