"""add initiator, target, duration_ms columns to activity_events

Revision ID: 20260529_0013
Revises: 20260529_0012
Create Date: 2026-05-29
"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "20260529_0013"
down_revision = "20260529_0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("activity_events", sa.Column("initiator", sa.String(length=255), nullable=True))
    op.add_column("activity_events", sa.Column("target", sa.String(length=2048), nullable=True))
    op.add_column("activity_events", sa.Column("duration_ms", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("activity_events", "duration_ms")
    op.drop_column("activity_events", "target")
    op.drop_column("activity_events", "initiator")
