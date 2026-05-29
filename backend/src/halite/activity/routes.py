from __future__ import annotations

from fastapi import APIRouter, Query

from halite.activity.api_schemas import ActivityEventOut, ActivityListOut
from halite.activity.service import list_events
from halite.deps import CurrentUser, SessionDep
from halite.rbac.engine import check as rbac_check

router = APIRouter(prefix="/api/activity", tags=["activity"])

_CATEGORIES = ("job", "key", "minion")


def _allowed_categories(user) -> set[str]:
    return {c for c in _CATEGORIES if rbac_check(user, "view", f"{c}:*")}


@router.get("", response_model=ActivityListOut)
async def list_activity_route(
    db: SessionDep,
    user: CurrentUser,
    category: str | None = Query(default=None),
    minion_id: str | None = Query(default=None),
    event_type: str | None = Query(default=None),
    search: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> ActivityListOut:
    total, rows = await list_events(
        db,
        allowed_categories=_allowed_categories(user),
        category=category,
        minion_id=minion_id,
        event_type=event_type,
        search=search,
        limit=limit,
        offset=offset,
    )
    return ActivityListOut(
        total=total,
        events=[ActivityEventOut.model_validate(r, from_attributes=True) for r in rows],
    )
