"""app_settings singleton table

Revision ID: 20260527_0009
Revises: 20260527_0008
Create Date: 2026-05-27
"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "20260527_0009"
down_revision = "20260527_0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "app_settings",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("salt_api_url", sa.String(512), nullable=True),
        sa.Column("salt_api_username", sa.String(255), nullable=True),
        sa.Column("salt_api_password_encrypted", sa.Text, nullable=True),
        sa.Column("salt_api_verify", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("salt_api_eauth", sa.String(32), nullable=False, server_default="pam"),
        sa.Column("inventory_refresh_minutes", sa.Integer, nullable=False, server_default="0"),
        sa.Column("inventory_refresh_initial_delay_s", sa.Integer, nullable=False, server_default="30"),
        sa.Column("fleet_poll_interval_seconds", sa.Integer, nullable=False, server_default="0"),
        sa.Column("minion_state_keys_interval_seconds", sa.Integer, nullable=False, server_default="300"),
        sa.Column("minion_state_presence_interval_seconds", sa.Integer, nullable=False, server_default="60"),
        sa.Column("minion_state_grains_interval_seconds", sa.Integer, nullable=False, server_default="300"),
        sa.Column("minion_state_initial_delay_seconds", sa.Integer, nullable=False, server_default="10"),
        sa.Column("log_format", sa.String(8), nullable=False, server_default="json"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("id = 1", name="ck_app_settings_singleton"),
    )
    # Seed the singleton row. We use SQL's CURRENT_TIMESTAMP rather than a
    # Python-bound datetime because asyncpg refuses to coerce an ISO string
    # into a timestamptz, and binding a datetime via sa.text doesn't always
    # propagate the type. CURRENT_TIMESTAMP works on both Postgres + SQLite.
    op.execute(
        sa.text(
            "INSERT INTO app_settings (id, salt_api_verify, salt_api_eauth, "
            "inventory_refresh_minutes, inventory_refresh_initial_delay_s, "
            "fleet_poll_interval_seconds, minion_state_keys_interval_seconds, "
            "minion_state_presence_interval_seconds, minion_state_grains_interval_seconds, "
            "minion_state_initial_delay_seconds, log_format, updated_at) "
            "VALUES (1, TRUE, 'pam', 0, 30, 0, 300, 60, 300, 10, 'json', CURRENT_TIMESTAMP)"
        )
    )


def downgrade() -> None:
    op.drop_table("app_settings")
