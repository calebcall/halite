# backend/src/halite/inventory/schemas.py
"""Pydantic schemas for the inventory API.

The query DSL is intentionally a *structured filter* (not a parsed string) —
the frontend renders a form, serialises it to this shape, and the backend
turns each clause into either a SQL predicate (when cheap and indexed) or a
Python predicate applied to the post-SQL candidate set (when the operation
needs custom semantics, e.g. version comparison). This keeps the API stable
even as the storage layer gets smarter.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

# Same set of operators we accept everywhere a version compare is involved.
# Keep aligned with halite.inventory.version_compare.Op.
VersionOp = Literal["eq", "ne", "lt", "lte", "gt", "gte"]

# Salt target_types we plumb through to refresh.
TargetType = Literal["glob", "list", "pcre", "grain", "nodegroup", "compound"]


class VersionFilter(BaseModel):
    """A version comparison applied per-row in Python after SQL narrowing."""

    op: VersionOp
    value: str = Field(min_length=1, max_length=255)


class NameFilter(BaseModel):
    """A name-side filter. ``op="eq"`` becomes ``name = ?``;
    ``op="prefix"`` becomes ``name LIKE ? || '%'`` (cheap, hits the index);
    ``op="contains"`` becomes ``name LIKE '%' || ? || '%'`` (slower, full scan
    of the (name)-indexed range but acceptable at our fleet size).
    """

    op: Literal["eq", "prefix", "contains"] = "eq"
    value: str = Field(min_length=1, max_length=255)


class PackageQueryIn(BaseModel):
    """Filter for ``GET /api/inventory/packages``.

    At least one of ``name`` or ``minion_id`` MUST be supplied — we don't
    want to accidentally let the UI fetch the entire fleet's package list
    in one request. (A future "browse all" endpoint can lift this rule.)
    """

    name: NameFilter | None = None
    version: VersionFilter | None = None
    source: Literal["apt", "rpm", "pacman"] | None = None
    minion_id: str | None = Field(default=None, max_length=255)
    # Cap so a runaway browser tab can't OOM the server.
    limit: int = Field(default=500, ge=1, le=5000)
    offset: int = Field(default=0, ge=0)

    @field_validator("minion_id")
    @classmethod
    def _no_whitespace(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = v.strip()
        return v or None

    @model_validator(mode="after")
    def _require_name_or_minion(self) -> PackageQueryIn:
        # Cross-field guardrail: don't let the UI accidentally fetch the
        # whole fleet's package list in one request.
        if self.name is None and not self.minion_id:
            raise ValueError("PackageQueryIn requires at least one of: name, minion_id")
        return self


class PackageQueryHit(BaseModel):
    """One row in the response to a package query."""

    minion_id: str
    name: str
    version: str
    arch: str | None = None
    source: str | None = None
    collected_at: datetime


class PackageQueryOut(BaseModel):
    """Wrapper that lets us tack pagination metadata on later without breaking
    the wire format."""

    total: int
    hits: list[PackageQueryHit]
    # True when the SQL candidate set was truncated *before* the version
    # filter ran. Lets the UI tell the user "narrow your filter" instead of
    # silently lying about completeness.
    truncated: bool = False


class RefreshIn(BaseModel):
    """Body for ``POST /api/inventory/refresh``.

    ``target='*'`` + ``target_type='glob'`` means "every connected minion".
    Pin the target down if you want to refresh just one host."""

    target: str = Field(default="*", min_length=1, max_length=1024)
    target_type: TargetType = "glob"


class RefreshOut(BaseModel):
    minions_refreshed: int
    package_counts: dict[str, int]


# ---------- Aggregate views (drill-down API) ----------
#
# The UI lands on a *fleet-wide* package list with no filter required, so we
# expose two server-side aggregations:
#
#   1. ``PackageAggregate``  — one row per package name.
#   2. ``VersionAggregate``  — one row per (version, arch) of a given name.
#
# Going from aggregate row → the individual minions for one (name, version)
# uses the existing ``PackageQueryIn`` search endpoint with both filters set.


class PackageAggregate(BaseModel):
    """One row in the fleet-wide package list."""

    name: str
    minion_count: int  # distinct minions that have this package installed
    version_count: int  # distinct versions seen across the fleet
    last_seen: datetime  # most recent collected_at for any row with this name


class PackageAggregateOut(BaseModel):
    total: int
    items: list[PackageAggregate]


class VersionAggregate(BaseModel):
    """One row in the per-package version list."""

    version: str
    arch: str | None = None
    source: str | None = None
    minion_count: int


class VersionAggregateOut(BaseModel):
    name: str
    total: int
    items: list[VersionAggregate]
