"""command templates

Revision ID: 20260526_0005
Revises: 20260525_0004
Create Date: 2026-05-26

Adds personal command templates owned by users.id. Cross-dialect JSON
columns for args/kwargs (JSONB on postgres at the ORM layer; the migration
uses portable sa.JSON()). Unique (owner_user_id, name) prevents duplicate
template names per user.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260526_0005"
down_revision: str | None = "20260525_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "command_templates",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "owner_user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description", sa.String(500), nullable=False, server_default=""),
        sa.Column("target", sa.String(1024), nullable=False),
        sa.Column("target_type", sa.String(32), nullable=False, server_default="glob"),
        sa.Column("fun", sa.String(128), nullable=False),
        sa.Column("args", sa.JSON(), nullable=False),
        sa.Column("kwargs", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("owner_user_id", "name", name="uq_template_owner_name"),
    )
    op.create_index(
        "ix_command_templates_owner_user_id",
        "command_templates",
        ["owner_user_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_command_templates_owner_user_id", table_name="command_templates")
    op.drop_table("command_templates")
