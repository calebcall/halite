"""add changed column to activity_events

Revision ID: 20260529_0012
Revises: 20260529_0011
Create Date: 2026-05-29
"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "20260529_0012"
down_revision = "20260529_0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("activity_events", sa.Column("changed", sa.Boolean(), nullable=True))


def downgrade() -> None:
    op.drop_column("activity_events", "changed")
