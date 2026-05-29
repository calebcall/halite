"""activity_events table + event stream settings

Revision ID: 20260529_0011
Revises: 20260527_0010
Create Date: 2026-05-29
"""
from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision = "20260529_0011"
down_revision = "20260527_0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    pk_type = sa.BigInteger().with_variant(sa.Integer(), "sqlite")
    json_type = sa.JSON().with_variant(JSONB(), "postgresql")
    op.create_table(
        "activity_events",
        sa.Column("id", pk_type, primary_key=True, autoincrement=True),
        sa.Column("ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column("category", sa.String(32), nullable=False),
        sa.Column("event_type", sa.String(32), nullable=False),
        sa.Column("minion_id", sa.String(255), nullable=True),
        sa.Column("jid", sa.String(64), nullable=True),
        sa.Column("fun", sa.String(128), nullable=True),
        sa.Column("success", sa.Boolean(), nullable=True),
        sa.Column("summary", sa.String(512), nullable=False),
        sa.Column("raw", json_type, nullable=True),
    )
    op.create_index("ix_activity_events_ts", "activity_events", ["ts"])
    op.create_index("ix_activity_events_category_ts", "activity_events", ["category", "ts"])
    op.create_index("ix_activity_events_minion_ts", "activity_events", ["minion_id", "ts"])
    op.create_index("ix_activity_events_jid", "activity_events", ["jid"])

    with op.batch_alter_table("app_settings") as batch:
        batch.add_column(
            sa.Column("event_stream_enabled", sa.Boolean(), nullable=False, server_default=sa.false())
        )
        batch.add_column(
            sa.Column("event_stream_retention_days", sa.Integer(), nullable=False, server_default="30")
        )


def downgrade() -> None:
    with op.batch_alter_table("app_settings") as batch:
        batch.drop_column("event_stream_retention_days")
        batch.drop_column("event_stream_enabled")
    op.drop_index("ix_activity_events_jid", "activity_events")
    op.drop_index("ix_activity_events_minion_ts", "activity_events")
    op.drop_index("ix_activity_events_category_ts", "activity_events")
    op.drop_index("ix_activity_events_ts", "activity_events")
    op.drop_table("activity_events")
