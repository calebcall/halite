# backend/src/halite/inventory/models.py
"""SQLAlchemy ORM for fleet inventory.

Design notes
------------

* **Current-only**: there is exactly one row per ``(minion_id, name, arch)``
  in ``inventory_package``. A refresh of a minion replaces all of its rows
  for that facet (delete-then-insert, or upsert + tombstone — see
  ``service.refresh_packages``). History intentionally not modeled in phase 1.
* **No FK to a minions table**: minions in Halite aren't a persistent entity
  with a row in our DB — they're whatever the salt-master reports. Storing
  ``minion_id`` as a plain string keeps the inventory tables usable when a
  minion comes and goes from the master's key list. Deletion of stale rows
  happens via ``inventory_snapshot.collected_at`` rather than referential
  cascade.
* **Per-facet snapshot row**: ``inventory_snapshot`` records the last time we
  fetched ``packages`` (or any other facet) for a minion, plus the salt jid
  that produced the data. Useful for "show me staleness" badges and for the
  scheduler to decide who to refresh next.
* **Indexing**: queries like ``WHERE name = 'openssh-server' AND version <= ?``
  hit ``ix_pkg_name``. The version compare is finished in Python (see
  ``halite.inventory.version_compare``).
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from halite.db import Base

# SQLite-friendly BIGINT autoincrement (same pattern as audit_log).
_pk_type = BigInteger().with_variant(Integer(), "sqlite")


class InventorySnapshot(Base):
    """One row per (minion, facet) — tracks the last successful collection."""

    __tablename__ = "inventory_snapshot"

    id: Mapped[int] = mapped_column(_pk_type, primary_key=True, autoincrement=True)
    minion_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    facet: Mapped[str] = mapped_column(String(32), nullable=False)
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    salt_jid: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # Number of items in this snapshot. Saves a COUNT(*) at read time.
    item_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    __table_args__ = (
        UniqueConstraint("minion_id", "facet", name="uq_inventory_snapshot_minion_facet"),
    )


class InventoryPackage(Base):
    """One row per installed system package per minion. ``source`` records the
    package manager (``apt``, ``dnf``, ``yum``, ``pacman``, ``zypper``, ...).
    """

    __tablename__ = "inventory_package"

    id: Mapped[int] = mapped_column(_pk_type, primary_key=True, autoincrement=True)
    minion_id: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    version: Mapped[str] = mapped_column(String(255), nullable=False)
    # ``arch`` is None when the source pkg manager doesn't expose one (or it's
    # always the host arch). dpkg ships per-architecture rows; rpm too. pacman
    # is single-arch.
    arch: Mapped[str | None] = mapped_column(String(32), nullable=True)
    source: Mapped[str | None] = mapped_column(String(32), nullable=True)
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        # A given (minion, package, arch) is unique — the host package manager
        # can only have one installed version of a fully-qualified name at a
        # time. (Debian's multi-arch case is exactly why ``arch`` is part of
        # the key.)
        UniqueConstraint("minion_id", "name", "arch", name="uq_inventory_pkg_minion_name_arch"),
    )
