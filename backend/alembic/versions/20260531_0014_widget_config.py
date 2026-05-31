"""add per-deployment activity widget config columns to app_settings

Revision ID: 20260531_0014
Revises: 20260529_0013
Create Date: 2026-05-31
"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "20260531_0014"
down_revision = "20260529_0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "app_settings",
        sa.Column("widget_hide_dispatch", sa.Boolean, nullable=False, server_default=sa.true()),
    )
    op.add_column(
        "app_settings",
        sa.Column("widget_hide_routine", sa.Boolean, nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "app_settings",
        sa.Column("widget_show_jobs", sa.Boolean, nullable=False, server_default=sa.true()),
    )
    op.add_column(
        "app_settings",
        sa.Column("widget_show_keys", sa.Boolean, nullable=False, server_default=sa.true()),
    )
    op.add_column(
        "app_settings",
        sa.Column("widget_show_minions", sa.Boolean, nullable=False, server_default=sa.true()),
    )
    op.add_column(
        "app_settings",
        sa.Column("widget_event_count", sa.Integer, nullable=False, server_default="6"),
    )
    op.add_column(
        "app_settings",
        sa.Column("widget_heartbeat_minutes", sa.Integer, nullable=False, server_default="60"),
    )


def downgrade() -> None:
    op.drop_column("app_settings", "widget_heartbeat_minutes")
    op.drop_column("app_settings", "widget_event_count")
    op.drop_column("app_settings", "widget_show_minions")
    op.drop_column("app_settings", "widget_show_keys")
    op.drop_column("app_settings", "widget_show_jobs")
    op.drop_column("app_settings", "widget_hide_routine")
    op.drop_column("app_settings", "widget_hide_dispatch")
