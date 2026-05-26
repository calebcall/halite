"""inventory tables

Revision ID: 20260525_0004
Revises: 20260519_0003
Create Date: 2026-05-25

Adds the phase-1 inventory schema: a per-(minion, facet) snapshot row and a
per-package row keyed by (minion, name, arch). See
``halite.inventory.models`` for the full design rationale.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260525_0004"
down_revision: str | None = "20260519_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "inventory_snapshot",
        sa.Column(
            "id",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            primary_key=True,
            autoincrement=True,
        ),
        sa.Column("minion_id", sa.String(255), nullable=False),
        sa.Column("facet", sa.String(32), nullable=False),
        sa.Column("collected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("salt_jid", sa.String(64), nullable=True),
        sa.Column("item_count", sa.Integer(), nullable=False, server_default="0"),
        sa.UniqueConstraint("minion_id", "facet", name="uq_inventory_snapshot_minion_facet"),
    )
    op.create_index("ix_inventory_snapshot_minion", "inventory_snapshot", ["minion_id"])
    op.create_index(
        "ix_inventory_snapshot_facet_collected",
        "inventory_snapshot",
        ["facet", sa.text("collected_at DESC")],
    )

    op.create_table(
        "inventory_package",
        sa.Column(
            "id",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            primary_key=True,
            autoincrement=True,
        ),
        sa.Column("minion_id", sa.String(255), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("version", sa.String(255), nullable=False),
        sa.Column("arch", sa.String(32), nullable=True),
        sa.Column("source", sa.String(32), nullable=True),
        sa.Column("collected_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("minion_id", "name", "arch", name="uq_inventory_pkg_minion_name_arch"),
    )
    # The two hot query shapes:
    #   (1) "which servers have package X (any version)?"  -> ix on (name)
    #   (2) "what packages does minion Y have?"            -> ix on (minion_id)
    # Both also serve as the prefix for the unique constraint, so we get the
    # minion+name composite for free from #2.
    op.create_index("ix_inventory_pkg_name", "inventory_package", ["name"])
    op.create_index("ix_inventory_pkg_minion", "inventory_package", ["minion_id"])


def downgrade() -> None:
    op.drop_index("ix_inventory_pkg_minion", table_name="inventory_package")
    op.drop_index("ix_inventory_pkg_name", table_name="inventory_package")
    op.drop_table("inventory_package")
    op.drop_index("ix_inventory_snapshot_facet_collected", table_name="inventory_snapshot")
    op.drop_index("ix_inventory_snapshot_minion", table_name="inventory_snapshot")
    op.drop_table("inventory_snapshot")
