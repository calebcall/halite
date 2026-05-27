"""highstate_runs table

Revision ID: 20260526_0007
Revises: 20260526_0006
Create Date: 2026-05-26
"""
from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision = "20260526_0007"
down_revision = "20260526_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "highstate_runs",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("minion_id", sa.String(255), nullable=False),
        sa.Column("jid", sa.String(64), nullable=False),
        sa.Column("fun", sa.String(64), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("pass_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("fail_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("change_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("total_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("duration_ms", sa.Integer, nullable=False, server_default="0"),
        sa.Column("blocked", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column(
            "raw_result",
            sa.JSON().with_variant(JSONB(), "postgresql"),
            nullable=False,
        ),
        sa.UniqueConstraint("minion_id", "jid", name="uq_highstate_runs_minion_jid"),
    )
    op.create_index("ix_highstate_runs_completed_at", "highstate_runs", ["completed_at"])
    op.create_index(
        "ix_highstate_runs_minion_completed",
        "highstate_runs",
        ["minion_id", "completed_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_highstate_runs_minion_completed", "highstate_runs")
    op.drop_index("ix_highstate_runs_completed_at", "highstate_runs")
    op.drop_table("highstate_runs")
