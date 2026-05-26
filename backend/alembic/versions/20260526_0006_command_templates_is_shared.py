"""command templates: is_shared column

Revision ID: 20260526_0006
Revises: 20260526_0005
Create Date: 2026-05-26

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260526_0006"
down_revision: str | None = "20260526_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("command_templates") as batch:
        batch.add_column(
            sa.Column(
                "is_shared",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("command_templates") as batch:
        batch.drop_column("is_shared")
