from __future__ import annotations

import uuid
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy import Boolean, DateTime, ForeignKey, String, UniqueConstraint, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from halite.db import Base


class CommandTemplate(Base):
    """Personal saved command template owned by a user.

    Stores the salt-API call shape (target/target_type/fun/args/kwargs) so a
    user can re-run common commands from the UI without retyping. Scoped per
    user via ``owner_user_id`` with a unique (owner, name) so the same person
    can't have two templates with the same display name.
    """

    __tablename__ = "command_templates"
    __table_args__ = (
        UniqueConstraint("owner_user_id", "name", name="uq_template_owner_name"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    owner_user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    target: Mapped[str] = mapped_column(String(1024), nullable=False)
    target_type: Mapped[str] = mapped_column(String(32), nullable=False, default="glob")
    fun: Mapped[str] = mapped_column(String(128), nullable=False)
    # Cross-dialect JSON: JSONB on postgres, JSON elsewhere (sqlite for tests).
    args: Mapped[list] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"),
        nullable=False,
        default=list,
    )
    kwargs: Mapped[dict] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"),
        nullable=False,
        default=dict,
    )
    is_shared: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=sa.false(),
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
