from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse

from halite.activity.api_schemas import ActivityEventOut, ActivityListOut
from halite.activity.service import list_events
from halite.deps import CurrentUser, SessionDep
from halite.rbac.engine import check as rbac_check

router = APIRouter(prefix="/api/activity", tags=["activity"])

_CATEGORIES = ("job", "key", "minion")
_KEEPALIVE_S = 20.0


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
    hide_routine: bool = Query(default=False),
    since_minutes: int | None = Query(default=None, ge=1, le=10080),
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
        hide_routine=hide_routine,
        since_minutes=since_minutes,
        limit=limit,
        offset=offset,
    )
    return ActivityListOut(
        total=total,
        events=[ActivityEventOut.model_validate(r, from_attributes=True) for r in rows],
    )


def _sse(event: dict) -> str:
    payload = {
        k: event.get(k)
        for k in ("category", "event_type", "minion_id", "jid", "fun", "success", "changed", "summary")
    }
    return f"data: {json.dumps(payload)}\n\n"


@router.get("/stream")
async def stream_activity_route(request: Request, user: CurrentUser):
    runtime = getattr(request.app.state, "runtime", None)
    hub = getattr(runtime, "event_hub", None) if runtime else None
    if hub is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Event stream not enabled")
    allowed = _allowed_categories(user)
    if not allowed:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Forbidden")

    queue = hub.subscribe()

    async def gen():
        try:
            for ev in hub.recent():
                if ev.get("category") in allowed:
                    yield _sse(ev)
            while True:
                if await request.is_disconnected():
                    break
                try:
                    ev = await asyncio.wait_for(queue.get(), timeout=_KEEPALIVE_S)
                except TimeoutError:
                    yield ": keepalive\n\n"
                    continue
                if ev.get("category") in allowed:
                    yield _sse(ev)
        finally:
            hub.unsubscribe(queue)

    # SSE anti-buffering headers. Without these, reverse proxies (nginx and
    # friends) buffer the streamed response and the browser receives nothing
    # until the connection closes — the feed then only updates on page refresh
    # via the REST query. `X-Accel-Buffering: no` disables nginx proxy
    # buffering; `Cache-Control: no-cache` stops intermediaries from caching.
    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
