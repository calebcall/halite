from __future__ import annotations

from datetime import datetime

import sqlalchemy as sa
from sqlalchemy import Boolean, CheckConstraint, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from halite.db import Base


class AppSettings(Base):
    """Singleton row of runtime-tunable settings. The ``id`` column is
    constrained to 1 so there can only ever be one row."""

    __tablename__ = "app_settings"
    __table_args__ = (
        CheckConstraint("id = 1", name="ck_app_settings_singleton"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)

    salt_api_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    salt_api_username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    salt_api_password_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    salt_api_verify: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    salt_api_eauth: Mapped[str] = mapped_column(String(32), nullable=False, default="pam")

    inventory_refresh_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    inventory_refresh_initial_delay_s: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    fleet_poll_interval_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    jobs_poll_interval_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    minion_state_keys_interval_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=300)
    minion_state_presence_interval_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=60)
    minion_state_grains_interval_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=300)
    minion_state_initial_delay_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=10)

    event_stream_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=sa.false()
    )
    event_stream_retention_days: Mapped[int] = mapped_column(
        Integer, nullable=False, default=30, server_default="30"
    )

    log_format: Mapped[str] = mapped_column(String(8), nullable=False, default="json")

    widget_hide_dispatch: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=sa.true()
    )
    widget_hide_routine: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=sa.false()
    )
    widget_show_jobs: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=sa.true()
    )
    widget_show_keys: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=sa.true()
    )
    widget_show_minions: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=sa.true()
    )
    widget_event_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=6, server_default="6"
    )
    widget_heartbeat_minutes: Mapped[int] = mapped_column(
        Integer, nullable=False, default=60, server_default="60"
    )

    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
