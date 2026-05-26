# backend/src/halite/inventory/routes.py
"""HTTP surface for inventory queries and refresh.

Two routes:

* ``POST /api/inventory/packages/search`` — POST not GET because the filter
  body is a small JSON object with nested clauses; trying to encode that as
  query-string parameters fights the typed-client generator and the audit
  story (POST bodies show up cleanly in the audit log; query strings get
  truncated in some webserver logs).

* ``POST /api/inventory/refresh`` — kicks off a fan-out and writes audit on
  the result. Long-running (a few seconds for a fleet-wide refresh), but the
  ``pkg.list_pkgs`` call lives inside the request handler — we hold the HTTP
  connection until salt-api responds. Phase 6 introduces a background
  scheduler so the UI doesn't have to drive every refresh.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, status

from halite.audit.writer import record as audit_record
from halite.db import SessionDep
from halite.deps import CurrentUser, require_perm
from halite.inventory.schemas import (
    PackageAggregateOut,
    PackageQueryIn,
    PackageQueryOut,
    RefreshIn,
    RefreshOut,
    VersionAggregateOut,
)
from halite.inventory.service import (
    aggregate_packages,
    aggregate_versions,
    refresh_packages,
    search_packages,
)
from halite.salt.client import SaltAPIError, SaltAPIUnavailable
from halite.salt.deps import salt_client_or_503, wrap_salt_errors

router = APIRouter(prefix="/api/inventory", tags=["inventory"])

# ---------- read endpoints ----------
#
# The drill-down lives across three endpoints:
#
#   GET  /packages                       — fleet-wide aggregate (level 1)
#   GET  /packages/{name}/versions       — per-package version aggregate (level 2)
#   POST /packages/search                — row-level rows (level 3 + power query)
#
# Levels 1 and 2 are GETs because their inputs are simple scalars
# (query strings + path components) and they're naturally cacheable.
# Level 3 stayed a POST because its filter body has nested structure
# (NameFilter / VersionFilter objects) that doesn't encode pleasantly into
# query strings.


@router.get(
    "/packages",
    response_model=PackageAggregateOut,
    dependencies=[require_perm("view", "inventory:*")],
)
async def list_packages_route(
    db: SessionDep,
    q: str | None = None,
    source: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> PackageAggregateOut:
    """Fleet-wide aggregate: one row per package name. Default landing view."""
    if limit < 1 or limit > 5000:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "limit out of range")
    if offset < 0:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "offset must be ≥ 0")
    return await aggregate_packages(
        db,
        name_query=q,
        source=source,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/packages/{name}/versions",
    response_model=VersionAggregateOut,
    dependencies=[require_perm("view", "inventory:*")],
)
async def list_versions_route(
    name: str,
    db: SessionDep,
    source: str | None = None,
) -> VersionAggregateOut:
    """All distinct versions of one named package, with per-version minion counts."""
    return await aggregate_versions(db, name=name, source=source)


@router.post(
    "/packages/search",
    response_model=PackageQueryOut,
    dependencies=[require_perm("view", "inventory:*")],
)
async def search_packages_route(
    payload: PackageQueryIn,
    db: SessionDep,
) -> PackageQueryOut:
    """Row-level package search. Used by level 3 (minions with one specific
    name+version) and as a power-user query endpoint (version comparison,
    multi-field filter)."""
    return await search_packages(db, payload)


@router.post(
    "/refresh",
    response_model=RefreshOut,
    dependencies=[require_perm("collect", "inventory:*")],
)
async def refresh_route(
    payload: RefreshIn,
    request: Request,
    db: SessionDep,
    actor: CurrentUser,
) -> RefreshOut:
    client = salt_client_or_503(request)
    try:
        counts = await refresh_packages(
            db,
            client,
            target=payload.target,
            target_type=payload.target_type,
        )
    except (SaltAPIUnavailable, SaltAPIError) as exc:
        http_exc = wrap_salt_errors(exc)
        await audit_record(
            db,
            user_id=actor.id,
            action="inventory.refresh",
            resource=f"inventory:packages:{payload.target}",
            args_json=payload.model_dump(mode="json"),
            salt_jid=None,
            decision="deny",
            result_code=http_exc.status_code,
        )
        await db.commit()
        raise http_exc from None

    await audit_record(
        db,
        user_id=actor.id,
        action="inventory.refresh",
        resource=f"inventory:packages:{payload.target}",
        args_json={**payload.model_dump(mode="json"), "minions": list(counts.keys())},
        salt_jid=None,
        decision="allow",
        result_code=200,
    )
    await db.commit()

    if not counts:
        # Salt-api returned no usable rows for any minion. That's not a
        # transport error (we'd have raised above), it's a "nobody responded
        # or everybody returned junk" — surface as 502 so the UI can show a
        # red panel rather than a green-but-empty "0 minions refreshed".
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            "No minions responded with usable package data.",
        )

    return RefreshOut(
        minions_refreshed=len(counts),
        package_counts=counts,
    )
