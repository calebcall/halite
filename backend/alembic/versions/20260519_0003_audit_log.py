"""audit log

Revision ID: 20260519_0003
Revises: 20260519_0002
Create Date: 2026-05-19

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260519_0003"
down_revision: Union[str, None] = "20260519_0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "audit_log",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("action", sa.String(128), nullable=False),
        sa.Column("resource", sa.String(255), nullable=False),
        sa.Column("args_json", sa.JSON(), nullable=True),
        sa.Column("salt_jid", sa.String(64), nullable=True),
        sa.Column("decision", sa.String(16), nullable=False),
        sa.Column("result_code", sa.Integer(), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_index("ix_audit_at", "audit_log", [sa.text("at DESC")])
    op.create_index("ix_audit_user_at", "audit_log", ["user_id", sa.text("at DESC")])
    op.create_index("ix_audit_action_at", "audit_log", ["action", sa.text("at DESC")])


def downgrade() -> None:
    op.drop_index("ix_audit_action_at", table_name="audit_log")
    op.drop_index("ix_audit_user_at", table_name="audit_log")
    op.drop_index("ix_audit_at", table_name="audit_log")
    op.drop_table("audit_log")
