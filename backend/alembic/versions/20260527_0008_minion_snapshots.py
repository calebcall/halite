"""minion_snapshots table

Revision ID: 20260527_0008
Revises: 20260526_0007
Create Date: 2026-05-27
"""
from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision = "20260527_0008"
down_revision = "20260526_0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "minion_snapshots",
        sa.Column("minion_id", sa.String(255), primary_key=True),
        sa.Column("key_status", sa.String(16), nullable=False),
        sa.Column("online", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("primary_ip", sa.String(64), nullable=True),
        sa.Column("os", sa.String(64), nullable=True),
        sa.Column("os_family", sa.String(32), nullable=True),
        sa.Column("osrelease", sa.String(64), nullable=True),
        sa.Column("kernel", sa.String(32), nullable=True),
        sa.Column("kernelrelease", sa.String(64), nullable=True),
        sa.Column("virtual_type", sa.String(32), nullable=True),
        sa.Column("num_cpus", sa.Integer, nullable=True),
        sa.Column("mem_total_mb", sa.Integer, nullable=True),
        sa.Column("saltversion", sa.String(32), nullable=True),
        sa.Column(
            "grains",
            sa.JSON().with_variant(JSONB(), "postgresql"),
            nullable=True,
        ),
        sa.Column("presence_refreshed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("keys_refreshed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("grains_refreshed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_minion_snapshots_key_status", "minion_snapshots", ["key_status"])
    op.create_index("ix_minion_snapshots_online", "minion_snapshots", ["online"])


def downgrade() -> None:
    op.drop_index("ix_minion_snapshots_online", "minion_snapshots")
    op.drop_index("ix_minion_snapshots_key_status", "minion_snapshots")
    op.drop_table("minion_snapshots")
