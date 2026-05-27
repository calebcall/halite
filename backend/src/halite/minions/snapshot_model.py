from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from halite.db import Base


class MinionSnapshot(Base):
    __tablename__ = "minion_snapshots"

    minion_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    key_status: Mapped[str] = mapped_column(String(16), nullable=False)
    online: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    primary_ip: Mapped[str | None] = mapped_column(String(64), nullable=True)

    os: Mapped[str | None] = mapped_column(String(64), nullable=True)
    os_family: Mapped[str | None] = mapped_column(String(32), nullable=True)
    osrelease: Mapped[str | None] = mapped_column(String(64), nullable=True)
    kernel: Mapped[str | None] = mapped_column(String(32), nullable=True)
    kernelrelease: Mapped[str | None] = mapped_column(String(64), nullable=True)
    virtual_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    num_cpus: Mapped[int | None] = mapped_column(Integer, nullable=True)
    mem_total_mb: Mapped[int | None] = mapped_column(Integer, nullable=True)
    saltversion: Mapped[str | None] = mapped_column(String(32), nullable=True)

    grains: Mapped[dict[str, Any] | None] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"), nullable=True
    )

    presence_refreshed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    keys_refreshed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    grains_refreshed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
