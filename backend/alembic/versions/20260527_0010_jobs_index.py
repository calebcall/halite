"""jobs_index table + jobs_poll_interval_seconds

Revision ID: 20260527_0010
Revises: 20260527_0009
Create Date: 2026-05-27
"""
from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision = "20260527_0010"
down_revision = "20260527_0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "jobs_index",
        sa.Column("jid", sa.String(64), primary_key=True),
        sa.Column("function", sa.String(128), nullable=False),
        sa.Column("target", sa.String(2048), nullable=True),
        sa.Column("target_type", sa.String(32), nullable=True),
        sa.Column("user", sa.String(255), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "arguments",
            sa.JSON().with_variant(JSONB(), "postgresql"),
            nullable=True,
        ),
    )
    op.create_index("ix_jobs_index_started_at", "jobs_index", ["started_at"])
    op.create_index("ix_jobs_index_function", "jobs_index", ["function"])

    with op.batch_alter_table("app_settings") as batch:
        batch.add_column(
            sa.Column(
                "jobs_poll_interval_seconds",
                sa.Integer,
                nullable=False,
                server_default="0",
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("app_settings") as batch:
        batch.drop_column("jobs_poll_interval_seconds")
    op.drop_index("ix_jobs_index_function", "jobs_index")
    op.drop_index("ix_jobs_index_started_at", "jobs_index")
    op.drop_table("jobs_index")
