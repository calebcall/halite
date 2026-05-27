from __future__ import annotations

from datetime import datetime
from typing import Any

import sqlalchemy as sa
from sqlalchemy import JSON, DateTime, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from halite.db import Base


class JobIndexEntry(Base):
    """One row per JID seen by the jobs-index poller. Records the metadata
    that ``runner.jobs.list_jobs`` returns. Per-minion results stay in
    salt's cache and are fetched live via ``runner.jobs.list_job`` on
    demand (Jobs detail page); we don't mirror those here."""

    __tablename__ = "jobs_index"
    __table_args__ = (
        sa.Index("ix_jobs_index_started_at", "started_at"),
        sa.Index("ix_jobs_index_function", "function"),
    )

    jid: Mapped[str] = mapped_column(String(64), primary_key=True)
    function: Mapped[str] = mapped_column(String(128), nullable=False)
    target: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    target_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    user: Mapped[str | None] = mapped_column(String(255), nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    arguments: Mapped[dict[str, Any] | None] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"), nullable=True
    )
