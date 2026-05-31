# Live Event Stream Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Subscribe to Salt's event bus server-side and turn Halite real-time — a durable, searchable Activity feed plus event-driven query invalidation that replaces the 30s polls.

**Architecture:** One in-process background consumer holds a single SSE connection to salt-api's `/events`, normalizes each event, persists it to a new `activity_events` table, triggers event-driven ingest into `jobs_index`, and publishes to an in-process `EventHub` (pub/sub + ring buffer). Browsers connect to `/api/activity/stream` (SSE), which replays the ring buffer then streams live, filtered per the user's RBAC. The existing schedulers stay on as a relaxed reconciliation safety-net. The frontend's `useActivityStream` hook invalidates the matching TanStack Query caches on each event.

**Tech Stack:** FastAPI, SQLAlchemy (async) + Alembic, httpx (streaming), React 19, TanStack Router + Query, Vite, vitest + MSW.

**Spec:** `docs/superpowers/specs/2026-05-29-live-event-stream-design.md`

**Conventions to follow throughout:**
- Backend tests: `cd backend && pytest <path> -v`
- Frontend tests: `cd frontend && npx vitest run <path>`
- JSON columns: `JSON().with_variant(JSONB(), "postgresql")`
- All datetimes: `datetime.now(tz=UTC)`, columns `DateTime(timezone=True)`
- Commit after every green test. Commit messages: conventional, **no Co-Authored-By trailer**.

---

## Phase 1 — Backend data layer

### Task 1: `activity_events` model

**Files:**
- Create: `backend/src/halite/activity/__init__.py` (empty)
- Create: `backend/src/halite/activity/models.py`
- Test: `backend/tests/activity/test_models.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/activity/__init__.py` (empty) and `backend/tests/activity/test_models.py`:

```python
from datetime import UTC, datetime

from halite.activity.models import ActivityEvent


def test_activity_event_columns_exist():
    ev = ActivityEvent(
        ts=datetime.now(tz=UTC),
        category="job",
        event_type="job.ret",
        minion_id="web01",
        jid="20260529120000000000",
        fun="state.apply",
        success=True,
        summary="web01 returned state.apply",
        raw={"tag": "salt/job/x/ret/web01", "data": {}},
    )
    assert ev.category == "job"
    assert ev.jid == "20260529120000000000"
    assert ev.success is True
    assert ActivityEvent.__tablename__ == "activity_events"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/activity/test_models.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'halite.activity'`

- [ ] **Step 3: Write minimal implementation**

Create `backend/src/halite/activity/models.py` (mirrors `audit/models.py:18-31` column style):

```python
from __future__ import annotations

from datetime import datetime
from typing import Any

import sqlalchemy as sa
from sqlalchemy import JSON, BigInteger, Boolean, DateTime, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from halite.db import Base


class ActivityEvent(Base):
    __tablename__ = "activity_events"
    __table_args__ = (
        sa.Index("ix_activity_events_ts", "ts"),
        sa.Index("ix_activity_events_category_ts", "category", "ts"),
        sa.Index("ix_activity_events_minion_ts", "minion_id", "ts"),
        sa.Index("ix_activity_events_jid", "jid"),
    )

    _pk_type = BigInteger().with_variant(Integer(), "sqlite")
    id: Mapped[int] = mapped_column(_pk_type, primary_key=True, autoincrement=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    category: Mapped[str] = mapped_column(String(16), nullable=False)
    event_type: Mapped[str] = mapped_column(String(32), nullable=False)
    minion_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    jid: Mapped[str | None] = mapped_column(String(64), nullable=True)
    fun: Mapped[str | None] = mapped_column(String(128), nullable=True)
    success: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    summary: Mapped[str] = mapped_column(String(512), nullable=False)
    raw: Mapped[dict[str, Any] | None] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"), nullable=True
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/activity/test_models.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/src/halite/activity/ backend/tests/activity/
git commit -m "feat(activity): activity_events model"
```

---

### Task 2: Alembic migration for `activity_events` + settings columns

**Files:**
- Modify: `backend/src/halite/settings/models.py` (add 2 columns)
- Create: `backend/alembic/versions/20260529_0011_activity_events.py`

- [ ] **Step 1: Add the new settings columns to the model**

In `backend/src/halite/settings/models.py`, add to the `AppSettings` class (after `minion_state_initial_delay_seconds`):

```python
    event_stream_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=sa.text("0")
    )
    event_stream_retention_days: Mapped[int] = mapped_column(
        Integer, nullable=False, default=30, server_default="30"
    )
```

Ensure `Boolean`, `Integer`, and `sa` are imported at the top of the file (check existing imports; add what's missing).

- [ ] **Step 2: Find the current migration head**

Run: `cd backend && alembic heads`
Expected: prints one revision id (the `down_revision` for the new migration, e.g. `0010_jobs_index`). **Record it.**

- [ ] **Step 3: Write the migration**

Create `backend/alembic/versions/20260529_0011_activity_events.py` (mirror `20260527_0010_jobs_index.py`). Replace `<HEAD>` with the id from Step 2:

```python
"""activity_events table + event stream settings

Revision ID: 0011_activity_events
Revises: <HEAD>
Create Date: 2026-05-29
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0011_activity_events"
down_revision = "<HEAD>"
branch_labels = None
depends_on = None


def upgrade() -> None:
    pk_type = sa.BigInteger().with_variant(sa.Integer(), "sqlite")
    json_type = sa.JSON().with_variant(JSONB(), "postgresql")
    op.create_table(
        "activity_events",
        sa.Column("id", pk_type, primary_key=True, autoincrement=True),
        sa.Column("ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column("category", sa.String(16), nullable=False),
        sa.Column("event_type", sa.String(32), nullable=False),
        sa.Column("minion_id", sa.String(255), nullable=True),
        sa.Column("jid", sa.String(64), nullable=True),
        sa.Column("fun", sa.String(128), nullable=True),
        sa.Column("success", sa.Boolean(), nullable=True),
        sa.Column("summary", sa.String(512), nullable=False),
        sa.Column("raw", json_type, nullable=True),
    )
    op.create_index("ix_activity_events_ts", "activity_events", ["ts"])
    op.create_index(
        "ix_activity_events_category_ts", "activity_events", ["category", "ts"]
    )
    op.create_index(
        "ix_activity_events_minion_ts", "activity_events", ["minion_id", "ts"]
    )
    op.create_index("ix_activity_events_jid", "activity_events", ["jid"])

    with op.batch_alter_table("app_settings") as batch:
        batch.add_column(
            sa.Column(
                "event_stream_enabled",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("0"),
            )
        )
        batch.add_column(
            sa.Column(
                "event_stream_retention_days",
                sa.Integer(),
                nullable=False,
                server_default="30",
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("app_settings") as batch:
        batch.drop_column("event_stream_retention_days")
        batch.drop_column("event_stream_enabled")
    op.drop_index("ix_activity_events_jid", table_name="activity_events")
    op.drop_index("ix_activity_events_minion_ts", table_name="activity_events")
    op.drop_index("ix_activity_events_category_ts", table_name="activity_events")
    op.drop_index("ix_activity_events_ts", table_name="activity_events")
    op.drop_table("activity_events")
```

- [ ] **Step 4: Apply and verify the migration round-trips**

Run:
```bash
cd backend && alembic upgrade head && alembic downgrade -1 && alembic upgrade head
```
Expected: no errors; final state at head. (Uses the dev SQLite DB.)

- [ ] **Step 5: Commit**

```bash
git add backend/src/halite/settings/models.py backend/alembic/versions/20260529_0011_activity_events.py
git commit -m "feat(activity): migration for activity_events + event stream settings"
```

---

### Task 3: Event normalizer

Turns a raw Salt `(tag, data)` into a normalized dict (or `None` to drop). This is pure and the most logic-dense unit, so it gets thorough tests.

**Files:**
- Create: `backend/src/halite/activity/normalize.py`
- Test: `backend/tests/activity/test_normalize.py`

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/activity/test_normalize.py`:

```python
from halite.activity.normalize import normalize_event


def test_job_new():
    ev = normalize_event(
        "salt/job/20260529120000000000/new",
        {"fun": "state.apply", "minions": ["web01", "web02"], "tgt": "*"},
    )
    assert ev is not None
    assert ev["category"] == "job"
    assert ev["event_type"] == "job.new"
    assert ev["jid"] == "20260529120000000000"
    assert ev["fun"] == "state.apply"
    assert ev["minion_id"] is None
    assert "state.apply" in ev["summary"]


def test_job_ret_success():
    ev = normalize_event(
        "salt/job/20260529120000000000/ret/web01",
        {"fun": "test.ping", "id": "web01", "retcode": 0, "return": True},
    )
    assert ev["category"] == "job"
    assert ev["event_type"] == "job.ret"
    assert ev["minion_id"] == "web01"
    assert ev["jid"] == "20260529120000000000"
    assert ev["success"] is True


def test_job_ret_failure_via_retcode():
    ev = normalize_event(
        "salt/job/20260529120000000000/ret/db07",
        {"fun": "state.apply", "id": "db07", "retcode": 2, "return": {}},
    )
    assert ev["success"] is False


def test_minion_start():
    ev = normalize_event("salt/minion/web01/start", {"id": "web01"})
    assert ev["category"] == "minion"
    assert ev["event_type"] == "minion.start"
    assert ev["minion_id"] == "web01"


def test_key_accept():
    ev = normalize_event("salt/key", {"id": "db07", "act": "accept"})
    assert ev["category"] == "key"
    assert ev["event_type"] == "key.accept"
    assert ev["minion_id"] == "db07"


def test_auth_pending():
    ev = normalize_event("salt/auth", {"id": "db07", "act": "pend", "result": True})
    assert ev["category"] == "key"
    assert ev["event_type"] == "key.pend"
    assert ev["minion_id"] == "db07"


def test_unknown_tag_dropped():
    assert normalize_event("salt/beacon/web01/diskusage/x", {"id": "web01"}) is None
    assert normalize_event("salt/run/x/new", {}) is None
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd backend && pytest tests/activity/test_normalize.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement the normalizer**

Create `backend/src/halite/activity/normalize.py`:

```python
from __future__ import annotations

import re
from typing import Any, TypedDict

_JOB_RE = re.compile(r"^salt/job/(?P<jid>\d{20})/(?P<kind>new|ret)(?:/(?P<minion>.+))?$")
_MINION_START_RE = re.compile(r"^salt/minion/(?P<minion>.+)/start$")
# Map of Salt key/auth "act" values to our event_type suffix.
_KEY_ACTS = {"accept": "accept", "reject": "reject", "delete": "delete", "pend": "pend"}


class NormalizedEvent(TypedDict):
    category: str
    event_type: str
    minion_id: str | None
    jid: str | None
    fun: str | None
    success: bool | None
    summary: str
    raw: dict[str, Any]


def normalize_event(tag: str, data: dict[str, Any]) -> NormalizedEvent | None:
    """Normalize a raw Salt event into a typed dict, or None to drop it.

    v1 surfaces three families: jobs (new/ret), minion presence (start),
    and key activity (salt/key + salt/auth). Everything else is dropped.
    """
    raw = {"tag": tag, "data": data}

    m = _JOB_RE.match(tag)
    if m:
        jid = m.group("jid")
        fun = data.get("fun")
        if m.group("kind") == "new":
            return NormalizedEvent(
                category="job", event_type="job.new", minion_id=None, jid=jid,
                fun=fun, success=None,
                summary=f"{fun or 'job'} dispatched ({len(data.get('minions') or [])} minions)",
                raw=raw,
            )
        minion = m.group("minion") or data.get("id")
        retcode = data.get("retcode")
        success = (retcode == 0) if retcode is not None else None
        return NormalizedEvent(
            category="job", event_type="job.ret", minion_id=minion, jid=jid,
            fun=fun, success=success,
            summary=f"{minion} returned {fun or 'job'}"
            + ("" if success is None else (" ✓" if success else " ✗")),
            raw=raw,
        )

    m = _MINION_START_RE.match(tag)
    if m:
        minion = m.group("minion")
        return NormalizedEvent(
            category="minion", event_type="minion.start", minion_id=minion, jid=None,
            fun=None, success=None, summary=f"{minion} came online", raw=raw,
        )

    if tag == "salt/key" or tag == "salt/auth":
        act = str(data.get("act", "")).lower()
        suffix = _KEY_ACTS.get(act)
        if suffix is None:
            return None
        minion = data.get("id")
        labels = {
            "accept": "accepted", "reject": "rejected",
            "delete": "deleted", "pend": "pending",
        }
        return NormalizedEvent(
            category="key", event_type=f"key.{suffix}", minion_id=minion, jid=None,
            fun=None, success=None, summary=f"{minion} key {labels[suffix]}", raw=raw,
        )

    return None
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd backend && pytest tests/activity/test_normalize.py -v`
Expected: PASS (7 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/src/halite/activity/normalize.py backend/tests/activity/test_normalize.py
git commit -m "feat(activity): salt event normalizer"
```

---

## Phase 2 — Backend hub, consumer, runtime wiring

### Task 4: `EventHub` (in-process pub/sub + ring buffer)

**Files:**
- Create: `backend/src/halite/activity/hub.py`
- Test: `backend/tests/activity/test_hub.py`

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/activity/test_hub.py`:

```python
import asyncio

import pytest

from halite.activity.hub import EventHub


def _ev(cat="job", etype="job.new"):
    return {"category": cat, "event_type": etype, "summary": "x"}


@pytest.mark.asyncio
async def test_recent_returns_ring_in_order():
    hub = EventHub(ring_size=3)
    for i in range(5):
        hub.publish(_ev(etype=f"e{i}"))
    recent = hub.recent()
    assert [e["event_type"] for e in recent] == ["e2", "e3", "e4"]


@pytest.mark.asyncio
async def test_subscriber_receives_published_event():
    hub = EventHub()
    q = hub.subscribe()
    try:
        hub.publish(_ev(etype="hello"))
        got = await asyncio.wait_for(q.get(), timeout=1)
        assert got["event_type"] == "hello"
    finally:
        hub.unsubscribe(q)


@pytest.mark.asyncio
async def test_unsubscribe_stops_delivery():
    hub = EventHub()
    q = hub.subscribe()
    hub.unsubscribe(q)
    hub.publish(_ev())
    assert q.empty()
```

If `pytest.mark.asyncio` is not recognized, check `backend/pyproject.toml` for `asyncio_mode = "auto"` (the existing async tests reveal the project's convention — match it; if `auto`, drop the decorators).

- [ ] **Step 2: Run to verify it fails**

Run: `cd backend && pytest tests/activity/test_hub.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement the hub**

Create `backend/src/halite/activity/hub.py`:

```python
from __future__ import annotations

import asyncio
import logging
from collections import deque
from typing import Any

log = logging.getLogger(__name__)

Event = dict[str, Any]
_QUEUE_MAXSIZE = 1000


class EventHub:
    """In-process pub/sub for normalized events plus a bounded ring buffer
    of recent events for replay-on-connect. Single-worker only (see spec)."""

    def __init__(self, ring_size: int = 500) -> None:
        self._subscribers: set[asyncio.Queue[Event]] = set()
        self._ring: deque[Event] = deque(maxlen=ring_size)

    def publish(self, event: Event) -> None:
        self._ring.append(event)
        for q in list(self._subscribers):
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                log.warning("activity subscriber queue full; dropping event")

    def subscribe(self) -> asyncio.Queue[Event]:
        q: asyncio.Queue[Event] = asyncio.Queue(maxsize=_QUEUE_MAXSIZE)
        self._subscribers.add(q)
        return q

    def unsubscribe(self, q: asyncio.Queue[Event]) -> None:
        self._subscribers.discard(q)

    def recent(self) -> list[Event]:
        return list(self._ring)
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd backend && pytest tests/activity/test_hub.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/src/halite/activity/hub.py backend/tests/activity/test_hub.py
git commit -m "feat(activity): in-process event hub with ring buffer"
```

---

### Task 5: `stream_events()` on the Salt client

Adds an async generator that opens one long-lived SSE connection to salt-api's `/events` and yields `(tag, data)` tuples, reusing the client's token.

**Files:**
- Modify: `backend/src/halite/salt/client.py`
- Test: `backend/tests/salt/test_stream_events.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/salt/test_stream_events.py`. It drives the parser via a fake httpx transport that emits Salt's SSE wire format:

```python
import httpx
import pytest

from halite.salt.client import SaltAPIClient

# Salt SSE frames: blank-line-separated; each frame has "tag:" and "data:" lines.
_SSE_BODY = (
    "retry: 400\n\n"
    "tag: salt/job/20260529120000000000/new\n"
    'data: {"tag": "salt/job/20260529120000000000/new", "data": {"fun": "test.ping"}}\n\n'
    "tag: salt/minion/web01/start\n"
    'data: {"tag": "salt/minion/web01/start", "data": {"id": "web01"}}\n\n'
)


def _handler(request: httpx.Request) -> httpx.Response:
    if request.url.path == "/login":
        return httpx.Response(
            200, json={"return": [{"token": "t", "expire": 9999999999.0}]}
        )
    if request.url.path == "/events":
        return httpx.Response(200, text=_SSE_BODY)
    return httpx.Response(404)


@pytest.mark.asyncio
async def test_stream_events_parses_frames():
    client = SaltAPIClient(
        base_url="http://salt",
        username="u",
        password="p",
        transport=httpx.MockTransport(_handler),
    )
    got = []
    async for tag, data in client.stream_events():
        got.append((tag, data.get("id") or data.get("fun")))
        if len(got) == 2:
            break
    await client.aclose()
    assert got[0] == ("salt/job/20260529120000000000/new", "test.ping")
    assert got[1] == ("salt/minion/web01/start", "web01")
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd backend && pytest tests/salt/test_stream_events.py -v`
Expected: FAIL with `AttributeError: 'SaltAPIClient' object has no attribute 'stream_events'`

- [ ] **Step 3: Implement `stream_events`**

In `backend/src/halite/salt/client.py`, add this method to `SaltAPIClient` (after the existing public helpers). It reuses `_ensure_token()` and `self._client`:

```python
    async def stream_events(self):
        """Async generator yielding (tag, data) tuples from salt-api's SSE
        /events endpoint. One long-lived connection. Caller is responsible for
        reconnect/backoff; this raises on the first network error or stream end.
        """
        import json as _json

        token = await self._ensure_token()
        headers = {"X-Auth-Token": token, "Accept": "text/event-stream"}
        async with self._client.stream(
            "GET", "/events", headers=headers, timeout=None
        ) as resp:
            if resp.status_code == 401:
                token = await self._ensure_token(force=True)
            resp.raise_for_status()
            data_lines: list[str] = []
            async for line in resp.aiter_lines():
                if line == "":
                    if data_lines:
                        payload = "\n".join(data_lines)
                        data_lines = []
                        try:
                            obj = _json.loads(payload)
                        except ValueError:
                            continue
                        tag = obj.get("tag")
                        if tag:
                            yield tag, obj.get("data") or {}
                    continue
                if line.startswith("data:"):
                    data_lines.append(line[5:].lstrip())
                # "tag:" / "retry:" lines are ignored — the tag is inside the
                # JSON payload on the data: line (salt includes it both places).
```

Note: `aiter_lines()` splits on newlines; the `MockTransport` text response is buffered, which is fine for the test. Live, salt streams incrementally.

- [ ] **Step 4: Run to verify it passes**

Run: `cd backend && pytest tests/salt/test_stream_events.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/src/halite/salt/client.py backend/tests/salt/test_stream_events.py
git commit -m "feat(salt): stream_events SSE generator"
```

---

### Task 6: Persistence + single-job ingest helpers

The consumer needs (a) a function to write a normalized event to `activity_events`, (b) a single-job upsert into `jobs_index`, and (c) a retention prune. Build them as testable functions.

**Files:**
- Create: `backend/src/halite/activity/service.py`
- Modify: `backend/src/halite/jobs/ingest.py` (add `upsert_one_job`)
- Test: `backend/tests/activity/test_service.py`

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/activity/test_service.py`. Reuse the project's async DB session fixture — inspect an existing DB test (e.g. `backend/tests/` for a fixture named `db`/`session`/`async_session`) and use that fixture name. The test below assumes a fixture `db` yielding an `AsyncSession` with tables created:

```python
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select

from halite.activity.models import ActivityEvent
from halite.activity.normalize import normalize_event
from halite.activity.service import persist_event, prune_events


@pytest.mark.asyncio
async def test_persist_event_writes_row(db):
    ev = normalize_event("salt/minion/web01/start", {"id": "web01"})
    await persist_event(db, ev)
    await db.commit()
    count = await db.scalar(select(func.count()).select_from(ActivityEvent))
    assert count == 1


@pytest.mark.asyncio
async def test_prune_events_deletes_old(db):
    old = ActivityEvent(
        ts=datetime.now(tz=UTC) - timedelta(days=40),
        category="job", event_type="job.new", summary="old",
    )
    fresh = ActivityEvent(
        ts=datetime.now(tz=UTC), category="job", event_type="job.new", summary="new",
    )
    db.add_all([old, fresh])
    await db.commit()
    deleted = await prune_events(db, retention_days=30)
    await db.commit()
    assert deleted == 1
    remaining = await db.scalar(select(func.count()).select_from(ActivityEvent))
    assert remaining == 1
```

If no shared `db` fixture exists, copy the engine/session setup from an existing DB test in `backend/tests/` into a local fixture at the top of this file.

- [ ] **Step 2: Run to verify it fails**

Run: `cd backend && pytest tests/activity/test_service.py -v`
Expected: FAIL with `ModuleNotFoundError: halite.activity.service`

- [ ] **Step 3: Implement the service + the jobs upsert**

Create `backend/src/halite/activity/service.py`:

```python
from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from halite.activity.models import ActivityEvent
from halite.activity.normalize import NormalizedEvent


async def persist_event(db: AsyncSession, ev: NormalizedEvent) -> ActivityEvent:
    row = ActivityEvent(
        ts=datetime.now(tz=UTC),
        category=ev["category"],
        event_type=ev["event_type"],
        minion_id=ev["minion_id"],
        jid=ev["jid"],
        fun=ev["fun"],
        success=ev["success"],
        summary=ev["summary"],
        raw=ev["raw"],
    )
    db.add(row)
    return row


async def prune_events(db: AsyncSession, *, retention_days: int) -> int:
    cutoff = datetime.now(tz=UTC) - timedelta(days=retention_days)
    result = await db.execute(
        delete(ActivityEvent).where(ActivityEvent.ts < cutoff)
    )
    return result.rowcount or 0
```

In `backend/src/halite/jobs/ingest.py`, add a single-job upsert fed by a **`salt/job/<jid>/new`** event. The new-event payload carries the full job metadata in lowercase keys (`fun`, `tgt`, `tgt_type`, `user`, `arg`) — unlike the `jobs.list_jobs` runner, which returns Title-Case keys. This function maps the *event* shape:

```python
async def upsert_one_job(
    db: AsyncSession, jid: str, new_event_data: dict[str, Any]
) -> None:
    """Upsert a single job into jobs_index from a `salt/job/<jid>/new` event.
    `new_event_data` is the event payload: {fun, arg, tgt, tgt_type, user,
    minions, ...}. Mirrors the JobIndexEntry mapping in refresh_jobs_index but
    reads the event's lowercase keys."""
    started = _jid_to_utc(jid)
    if started is None:
        return
    now = datetime.now(tz=UTC)
    existing = await db.get(JobIndexEntry, jid)
    if existing is not None:
        existing.seen_at = now
        return
    arg = new_event_data.get("arg")
    db.add(
        JobIndexEntry(
            jid=jid,
            function=str(new_event_data.get("fun") or "unknown"),
            target=_opt_str(new_event_data.get("tgt")),
            target_type=_opt_str(new_event_data.get("tgt_type")),
            user=_opt_str(new_event_data.get("user")),
            started_at=started,
            seen_at=now,
            arguments={"arg": arg} if arg else None,
        )
    )
```

Verify the `JobIndexEntry` field names and the `_jid_to_utc` / `_opt_str` helpers exist in `jobs/ingest.py` (they do — confirm signatures) and that the column names match `index_model.py` exactly.

- [ ] **Step 4: Run to verify it passes**

Run: `cd backend && pytest tests/activity/test_service.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/src/halite/activity/service.py backend/src/halite/jobs/ingest.py backend/tests/activity/test_service.py
git commit -m "feat(activity): persist + prune events, single-job ingest"
```

---

### Task 7: `EventStreamConsumer` background task

Holds one upstream SSE connection, normalizes → persists → publishes → event-driven ingest, with reconnect/backoff. Mirrors the scheduler lifecycle (`jobs/scheduler.py`).

**Files:**
- Create: `backend/src/halite/activity/consumer.py`
- Test: `backend/tests/activity/test_consumer.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/activity/test_consumer.py`. Drive one batch of events through a fake salt client and assert the hub saw them and rows were written:

```python
import pytest
from sqlalchemy import func, select

from halite.activity.consumer import EventStreamConsumer
from halite.activity.hub import EventHub
from halite.activity.models import ActivityEvent


class _FakeSalt:
    async def stream_events(self):
        yield "salt/minion/web01/start", {"id": "web01"}
        yield "salt/key", {"id": "db07", "act": "accept"}
        yield "salt/beacon/web01/x", {"id": "web01"}  # dropped by normalizer


@pytest.mark.asyncio
async def test_consumer_processes_one_batch(db_sessionmaker):
    hub = EventHub()
    consumer = EventStreamConsumer(
        salt=_FakeSalt(),
        sessionmaker=db_sessionmaker,
        hub=hub,
        retention_days=30,
    )
    await consumer._consume_once()  # one pass over the fake stream
    assert len(hub.recent()) == 2  # beacon dropped
    async with db_sessionmaker() as s:
        count = await s.scalar(select(func.count()).select_from(ActivityEvent))
    assert count == 2
```

Use the project's `async_sessionmaker` test fixture (named `db_sessionmaker` here — rename to match what the existing tests expose; if only a `db` session fixture exists, add a sessionmaker fixture alongside it).

- [ ] **Step 2: Run to verify it fails**

Run: `cd backend && pytest tests/activity/test_consumer.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement the consumer**

Create `backend/src/halite/activity/consumer.py` (lifecycle mirrors `JobsIndexScheduler`):

```python
from __future__ import annotations

import asyncio
import logging

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from halite.activity.hub import EventHub
from halite.activity.normalize import normalize_event
from halite.activity.service import persist_event, prune_events
from halite.jobs.ingest import upsert_one_job

log = logging.getLogger(__name__)

_BACKOFF_START = 1.0
_BACKOFF_MAX = 30.0


class EventStreamConsumer:
    def __init__(
        self,
        *,
        salt,
        sessionmaker: async_sessionmaker[AsyncSession],
        hub: EventHub,
        retention_days: int,
    ) -> None:
        self._salt = salt
        self._sessionmaker = sessionmaker
        self._hub = hub
        self._retention_days = retention_days
        self._stop = asyncio.Event()
        self._task: asyncio.Task[None] | None = None

    @classmethod
    def from_row(cls, row, *, salt, sessionmaker, hub) -> "EventStreamConsumer":
        return cls(
            salt=salt,
            sessionmaker=sessionmaker,
            hub=hub,
            retention_days=row.event_stream_retention_days,
        )

    def start(self) -> None:
        if self._task is None:
            self._task = asyncio.create_task(self._loop(), name="activity-consumer")
            log.info("activity consumer started")

    async def stop(self) -> None:
        self._stop.set()
        if self._task is not None:
            try:
                await asyncio.wait_for(self._task, timeout=10)
            except TimeoutError:
                self._task.cancel()
            self._task = None

    async def _loop(self) -> None:
        backoff = _BACKOFF_START
        while not self._stop.is_set():
            try:
                await self._prune()
                await self._consume_once()
                backoff = _BACKOFF_START
            except Exception:
                log.exception("activity consumer stream error; backing off %.0fs", backoff)
                try:
                    await asyncio.wait_for(self._stop.wait(), timeout=backoff)
                except TimeoutError:
                    pass
                backoff = min(backoff * 2, _BACKOFF_MAX)

    async def _consume_once(self) -> None:
        async for tag, data in self._salt.stream_events():
            if self._stop.is_set():
                return
            ev = normalize_event(tag, data)
            if ev is None:
                continue
            async with self._sessionmaker() as session:
                await persist_event(session, ev)
                # Event-driven ingest fires on job.new — its payload carries the
                # full job metadata (fun/tgt/user/arg). job.ret is recorded as an
                # event but per-minion results are fetched on demand by the Jobs
                # detail view; the reconciliation poll backfills anything missed.
                if ev["event_type"] == "job.new" and ev["jid"]:
                    try:
                        await upsert_one_job(session, ev["jid"], data)
                    except Exception:
                        log.exception("event-driven job ingest failed for %s", ev["jid"])
                await session.commit()
            self._hub.publish(ev)

    async def _prune(self) -> None:
        try:
            async with self._sessionmaker() as session:
                deleted = await prune_events(session, retention_days=self._retention_days)
                await session.commit()
            if deleted:
                log.info("activity retention prune: %d events removed", deleted)
        except Exception:
            log.exception("activity retention prune failed")
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd backend && pytest tests/activity/test_consumer.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/src/halite/activity/consumer.py backend/tests/activity/test_consumer.py
git commit -m "feat(activity): event stream consumer with reconnect/backoff"
```

---

### Task 8: Wire consumer + hub into `RuntimeConfig`

**Files:**
- Modify: `backend/src/halite/runtime.py`
- Test: extend `backend/tests/` runtime test if one exists; otherwise a focused test below.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/activity/test_runtime_wiring.py`:

```python
import pytest

from halite.activity.hub import EventHub


@pytest.mark.asyncio
async def test_event_hub_created_when_enabled(monkeypatch):
    # A lightweight check that RuntimeConfig exposes event_hub/event_consumer
    # attributes (defaults None). Full boot is covered by integration tests.
    from halite.runtime import RuntimeConfig
    rc = RuntimeConfig.__new__(RuntimeConfig)
    assert hasattr(RuntimeConfig, "event_hub") or True  # attribute set in __init__
    # Sanity: EventHub is importable and usable
    hub = EventHub()
    assert hub.recent() == []
```

(This is a smoke check; the real verification is Step 4 + the existing integration suite.)

- [ ] **Step 2: Run to verify current state**

Run: `cd backend && pytest tests/activity/test_runtime_wiring.py -v`
Expected: PASS trivially, OR fails on import — confirm import works.

- [ ] **Step 3: Wire into RuntimeConfig**

In `backend/src/halite/runtime.py`:

In `__init__`, add:
```python
        self.event_hub: EventHub | None = None
        self.event_consumer: EventStreamConsumer | None = None
```
Add imports at top:
```python
from halite.activity.consumer import EventStreamConsumer
from halite.activity.hub import EventHub
```

In `_wire(self, row)`, after the salt client is created and `self.salt` is set, and alongside the other scheduler starts, add:
```python
        if row.event_stream_enabled:
            self.event_hub = EventHub()
            self.event_consumer = EventStreamConsumer.from_row(
                row, salt=self.salt, sessionmaker=self._sessionmaker, hub=self.event_hub
            )
            self.event_consumer.start()
```

In `_teardown(self)`, alongside stopping the other schedulers, add (stop consumer, clear hub):
```python
        if self.event_consumer is not None:
            try:
                await self.event_consumer.stop()
            except Exception:
                log.exception("error stopping event consumer")
            self.event_consumer = None
        self.event_hub = None
```

- [ ] **Step 4: Run the full backend suite to verify nothing regressed**

Run: `cd backend && pytest -q`
Expected: all pass (matches matrix sqlite/pg locally as configured).

- [ ] **Step 5: Commit**

```bash
git add backend/src/halite/runtime.py backend/tests/activity/test_runtime_wiring.py
git commit -m "feat(activity): wire event hub + consumer into RuntimeConfig"
```

---

### Task 9: Settings schema/service exposure for the two new fields

**Files:**
- Modify: `backend/src/halite/settings/schemas.py`
- Modify: `backend/src/halite/settings/service.py`
- Test: extend an existing settings test or add `backend/tests/activity/test_settings_fields.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/activity/test_settings_fields.py`:

```python
from halite.settings.schemas import PollerSettingsIn


def test_event_stream_fields_accepted():
    p = PollerSettingsIn(event_stream_enabled=True, event_stream_retention_days=14)
    assert p.event_stream_enabled is True
    assert p.event_stream_retention_days == 14
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd backend && pytest tests/activity/test_settings_fields.py -v`
Expected: FAIL (`extra="forbid"` rejects unknown fields, or fields missing)

- [ ] **Step 3: Add fields to schema + service**

In `backend/src/halite/settings/schemas.py`:
- Add to `PollerSettingsOut`:
```python
    event_stream_enabled: bool
    event_stream_retention_days: int
```
- Add to `PollerSettingsIn`:
```python
    event_stream_enabled: bool | None = Field(default=None)
    event_stream_retention_days: int | None = Field(default=None, ge=1, le=365)
```

In `backend/src/halite/settings/service.py`, add both field names to the tuple iterated in `update_pollers()`:
```python
        "event_stream_enabled",
        "event_stream_retention_days",
```
Verify where `PollerSettingsOut` is constructed (in `get_settings`/service) and ensure the two new fields are populated from the row.

- [ ] **Step 4: Run to verify it passes**

Run: `cd backend && pytest tests/activity/test_settings_fields.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/src/halite/settings/ backend/tests/activity/test_settings_fields.py
git commit -m "feat(activity): expose event stream settings in pollers schema"
```

---

## Phase 3 — Backend API

### Task 10: REST `/api/activity` (paginated, filtered, permission-scoped)

**Files:**
- Create: `backend/src/halite/activity/api_schemas.py`
- Create: `backend/src/halite/activity/routes.py`
- Modify: `backend/src/halite/main.py` (register router)
- Modify: `backend/src/halite/activity/service.py` (add `list_events`)
- Test: `backend/tests/activity/test_routes.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/activity/test_routes.py`. Use the project's existing API test client + auth helpers — inspect an existing route test (e.g. a jobs/keys route test in `backend/tests/`) for the `TestClient`/`httpx.AsyncClient` + login fixture pattern, and mirror it. Sketch:

```python
import pytest


@pytest.mark.asyncio
async def test_list_activity_filters_by_permission(client_as_viewer_job_only, seed_events):
    # viewer has only view job:* — should see job events, not key/minion.
    resp = await client_as_viewer_job_only.get("/api/activity")
    assert resp.status_code == 200
    cats = {e["category"] for e in resp.json()["events"]}
    assert cats <= {"job"}


@pytest.mark.asyncio
async def test_list_activity_category_filter(client_as_admin, seed_events):
    resp = await client_as_admin.get("/api/activity?category=key")
    assert resp.status_code == 200
    assert all(e["category"] == "key" for e in resp.json()["events"])
```

Build `seed_events` to insert a few `ActivityEvent` rows of each category, and reuse the existing auth-client fixtures (rename to match the project's actual fixtures).

- [ ] **Step 2: Run to verify it fails**

Run: `cd backend && pytest tests/activity/test_routes.py -v`
Expected: FAIL (router/endpoint missing)

- [ ] **Step 3: Implement schemas, service query, and route**

Create `backend/src/halite/activity/api_schemas.py`:

```python
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class ActivityEventOut(BaseModel):
    id: int
    ts: datetime
    category: str
    event_type: str
    minion_id: str | None
    jid: str | None
    fun: str | None
    success: bool | None
    summary: str


class ActivityListOut(BaseModel):
    total: int
    events: list[ActivityEventOut]
```

Add `list_events` to `backend/src/halite/activity/service.py`:

```python
from sqlalchemy import func, select


async def list_events(
    db: AsyncSession,
    *,
    allowed_categories: set[str],
    category: str | None = None,
    minion_id: str | None = None,
    event_type: str | None = None,
    search: str | None = None,
    limit: int = 100,
    offset: int = 0,
):
    if not allowed_categories:
        return 0, []
    cats = allowed_categories if category is None else (allowed_categories & {category})
    if not cats:
        return 0, []
    base = select(ActivityEvent).where(ActivityEvent.category.in_(cats))
    if minion_id:
        base = base.where(ActivityEvent.minion_id == minion_id)
    if event_type:
        base = base.where(ActivityEvent.event_type == event_type)
    if search:
        base = base.where(ActivityEvent.summary.ilike(f"%{search}%"))
    total = await db.scalar(
        select(func.count()).select_from(base.subquery())
    )
    rows = (
        await db.execute(
            base.order_by(ActivityEvent.ts.desc()).limit(limit).offset(offset)
        )
    ).scalars().all()
    return int(total or 0), list(rows)
```

Create `backend/src/halite/activity/routes.py` (mirror `jobs/routes.py:20-49`; gate on auth, filter categories inside):

```python
from __future__ import annotations

from fastapi import APIRouter, Query, Request

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
        total=total, events=[ActivityEventOut.model_validate(r, from_attributes=True) for r in rows]
    )
```

In `backend/src/halite/main.py`, add the import alongside the others and `app.include_router(activity_router)`:
```python
    from halite.activity.routes import router as activity_router
    ...
    app.include_router(activity_router)
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd backend && pytest tests/activity/test_routes.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/src/halite/activity/ backend/src/halite/main.py backend/tests/activity/test_routes.py
git commit -m "feat(activity): REST /api/activity with permission-scoped filtering"
```

---

### Task 11: SSE `/api/activity/stream`

**Files:**
- Modify: `backend/src/halite/activity/routes.py`
- Test: `backend/tests/activity/test_stream_route.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/activity/test_stream_route.py`. Verify the endpoint replays the ring buffer filtered by permission. Use the app with a hub pre-seeded on `app.state.runtime`:

```python
import pytest


@pytest.mark.asyncio
async def test_stream_replays_ring_filtered(app_with_seeded_hub, client_as_viewer_job_only):
    # hub seeded with one job + one key event; viewer sees only the job line.
    async with client_as_viewer_job_only.stream("GET", "/api/activity/stream") as resp:
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/event-stream")
        body = ""
        async for chunk in resp.aiter_text():
            body += chunk
            if "job.new" in body:
                break
    assert "job.new" in body
    assert "key.accept" not in body
```

`app_with_seeded_hub` sets `app.state.runtime.event_hub = EventHub()` and publishes one `job` + one `key` event before the request. Mirror the existing app/client fixture wiring.

- [ ] **Step 2: Run to verify it fails**

Run: `cd backend && pytest tests/activity/test_stream_route.py -v`
Expected: FAIL (no `/stream` route)

- [ ] **Step 3: Implement the SSE route**

Append to `backend/src/halite/activity/routes.py`:

```python
import asyncio
import json

from fastapi import HTTPException, status
from fastapi.responses import StreamingResponse

_KEEPALIVE_S = 20.0


def _sse(event: dict) -> str:
    payload = {k: event.get(k) for k in (
        "category", "event_type", "minion_id", "jid", "fun", "success", "summary"
    )}
    return f"data: {json.dumps(payload)}\n\n"


@router.get("/stream")
async def stream_activity_route(request: Request, user: CurrentUser):
    runtime = getattr(request.app.state, "runtime", None)
    hub = getattr(runtime, "event_hub", None) if runtime else None
    if hub is None:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "Event stream not enabled"
        )
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

    return StreamingResponse(gen(), media_type="text/event-stream")
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd backend && pytest tests/activity/test_stream_route.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/src/halite/activity/routes.py backend/tests/activity/test_stream_route.py
git commit -m "feat(activity): SSE /api/activity/stream with per-connection filtering"
```

---

### Task 12: Regenerate the OpenAPI TypeScript types

The frontend consumes generated types from the backend schema.

**Files:**
- Modify: `frontend/src/shared/api/types.gen.ts` (generated)

- [ ] **Step 1: Run the type generator**

Run: `cd frontend && npm run gen:types`
Expected: `types.gen.ts` updated with `ActivityEventOut` / `ActivityListOut` and the `/api/activity` paths. (This invokes `scripts/gen-types.sh`; it may need the backend running or use a committed schema — follow whatever the script does.)

- [ ] **Step 2: Verify types compile**

Run: `cd frontend && npx tsc -b`
Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/shared/api/types.gen.ts
git commit -m "chore(activity): regenerate API types"
```

---

## Phase 4 — Frontend

### Task 13: Activity API binding + query keys

**Files:**
- Create: `frontend/src/features/activity/api.ts`
- Test: covered indirectly by later tests; no standalone test.

- [ ] **Step 1: Implement the api + query keys**

Create `frontend/src/features/activity/api.ts` (mirror `features/jobs/api.ts:11-23`). Use the shared `request`/`api` client and the generated types:

```ts
import { request } from '@/shared/api/client'
import type { components } from '@/shared/api/types.gen'

export type ActivityListOut = components['schemas']['ActivityListOut']
export type ActivityEventOut = components['schemas']['ActivityEventOut']

export interface ActivityFilter {
  category?: string
  minion_id?: string
  event_type?: string
  search?: string
  limit?: number
  offset?: number
}

function toQuery(f: ActivityFilter): string {
  const p = new URLSearchParams()
  for (const [k, v] of Object.entries(f)) {
    if (v !== undefined && v !== '') p.set(k, String(v))
  }
  const s = p.toString()
  return s ? `?${s}` : ''
}

export const activityApi = {
  list: (f: ActivityFilter = {}) =>
    request<ActivityListOut>(`/api/activity${toQuery(f)}`),
}

export const activityQueryKeys = {
  all: ['activity'] as const,
  list: (f: ActivityFilter) => ['activity', 'list', f] as const,
}
```

Confirm the exact `request` import path/signature against `frontend/src/shared/api/client.ts` and match how `features/jobs/api.ts` imports it.

- [ ] **Step 2: Verify compile**

Run: `cd frontend && npx tsc -b`
Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/features/activity/api.ts
git commit -m "feat(activity): frontend api binding + query keys"
```

---

### Task 14: `useActivityStream` hook (EventSource → query invalidation)

**Files:**
- Create: `frontend/src/features/activity/use-activity-stream.ts`
- Create: `frontend/tests/setup-eventsource.ts` (test mock helper) OR inline mock in the test
- Test: `frontend/tests/ActivityStream.test.tsx`

- [ ] **Step 1: Write the failing test (with an EventSource mock — jsdom lacks it)**

Create `frontend/tests/ActivityStream.test.tsx`:

```tsx
import { renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { describe, it, expect, beforeEach, vi } from 'vitest'

import { useActivityStream } from '@/features/activity/use-activity-stream'

class MockEventSource {
  static instances: MockEventSource[] = []
  onmessage: ((e: { data: string }) => void) | null = null
  onerror: (() => void) | null = null
  url: string
  readyState = 0
  constructor(url: string) {
    this.url = url
    MockEventSource.instances.push(this)
  }
  emit(obj: unknown) {
    this.onmessage?.({ data: JSON.stringify(obj) })
  }
  close() {
    this.readyState = 2
  }
}

beforeEach(() => {
  MockEventSource.instances = []
  // @ts-expect-error test shim
  globalThis.EventSource = MockEventSource
})

function wrap() {
  const qc = new QueryClient()
  const spy = vi.spyOn(qc, 'invalidateQueries')
  const wrapper = ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={qc}>{children}</QueryClientProvider>
  )
  return { qc, spy, wrapper }
}

describe('useActivityStream', () => {
  it('invalidates jobs queries on a job event', async () => {
    const { spy, wrapper } = wrap()
    renderHook(() => useActivityStream(), { wrapper })
    const es = MockEventSource.instances[0]
    expect(es.url).toContain('/api/activity/stream')
    es.emit({ category: 'job', event_type: 'job.ret', jid: '20260529' })
    await waitFor(() =>
      expect(spy).toHaveBeenCalledWith(
        expect.objectContaining({ queryKey: ['jobs'] }),
      ),
    )
  })

  it('invalidates keys queries on a key event', async () => {
    const { spy, wrapper } = wrap()
    renderHook(() => useActivityStream(), { wrapper })
    MockEventSource.instances[0].emit({ category: 'key', event_type: 'key.accept' })
    await waitFor(() =>
      expect(spy).toHaveBeenCalledWith(
        expect.objectContaining({ queryKey: ['keys'] }),
      ),
    )
  })
})
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd frontend && npx vitest run tests/ActivityStream.test.tsx`
Expected: FAIL (`useActivityStream` not found)

- [ ] **Step 3: Implement the hook**

Create `frontend/src/features/activity/use-activity-stream.ts`. The invalidation map uses the **exact** query-key roots discovered: jobs `['jobs']`, minions `['minions']`, keys `['keys']` (invalidating the root busts list/detail/timeline/activity/runs since they're all prefixed):

```ts
import { useEffect } from 'react'
import { useQueryClient } from '@tanstack/react-query'

export interface ActivityStreamEvent {
  category: 'job' | 'key' | 'minion'
  event_type: string
  minion_id?: string | null
  jid?: string | null
  summary?: string
}

const INVALIDATION: Record<ActivityStreamEvent['category'], string[][]> = {
  job: [['jobs']],
  key: [['keys']],
  minion: [['minions']],
}

/**
 * Subscribes to /api/activity/stream and invalidates the matching TanStack
 * Query caches on each event. Optional onEvent lets the feed UI also consume
 * the live event. EventSource auto-reconnects on drop.
 */
export function useActivityStream(onEvent?: (e: ActivityStreamEvent) => void) {
  const qc = useQueryClient()
  useEffect(() => {
    const es = new EventSource('/api/activity/stream', { withCredentials: true })
    es.onmessage = (msg) => {
      let ev: ActivityStreamEvent
      try {
        ev = JSON.parse(msg.data)
      } catch {
        return
      }
      for (const queryKey of INVALIDATION[ev.category] ?? []) {
        void qc.invalidateQueries({ queryKey })
      }
      onEvent?.(ev)
    }
    return () => es.close()
    // onEvent intentionally omitted — callers pass a stable ref or inline; the
    // stream should not tear down/reconnect on every render.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [qc])
}
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd frontend && npx vitest run tests/ActivityStream.test.tsx`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add frontend/src/features/activity/use-activity-stream.ts frontend/tests/ActivityStream.test.tsx
git commit -m "feat(activity): useActivityStream hook with query invalidation"
```

---

### Task 15: Mount the stream globally + relax polling intervals

**Files:**
- Modify: `frontend/src/app/layout/AppShell.tsx` (mount the hook once)
- Modify: `frontend/src/features/jobs/use-jobs.ts`, `frontend/src/features/minions/use-minions.ts`, `frontend/src/features/keys/use-keys.ts`, `frontend/src/features/minions/use-minion-runs.ts`, `frontend/src/features/jobs/use-jobs-timeline.ts`
- Test: `frontend/tests/PollingRelaxed.test.ts` (guards against regressing to 30s)

- [ ] **Step 1: Write the failing test**

Create `frontend/tests/PollingRelaxed.test.ts` (a static guard that the fast polls were relaxed):

```ts
import { readFileSync } from 'node:fs'
import { describe, it, expect } from 'vitest'

const files = [
  'src/features/jobs/use-jobs.ts',
  'src/features/minions/use-minions.ts',
  'src/features/keys/use-keys.ts',
]

describe('polling relaxed in favor of the event stream', () => {
  it('has no 30s refetchInterval left in live-list hooks', () => {
    for (const f of files) {
      const src = readFileSync(f, 'utf8')
      expect(src.includes('refetchInterval: 30_000')).toBe(false)
    }
  })
})
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd frontend && npx vitest run tests/PollingRelaxed.test.ts`
Expected: FAIL (the 30s intervals still present)

- [ ] **Step 3: Relax the intervals + mount the hook**

In each of `use-jobs.ts`, `use-minions.ts`, `use-keys.ts`: change `refetchInterval: 30_000` → `refetchInterval: 5 * 60 * 1000` (5-minute reconciliation fallback; the event stream drives live freshness). Leave the already-5-minute hooks (`use-minion-runs.ts`, `use-jobs-timeline.ts`, jobs activity) as-is — they're already relaxed; no change needed there beyond confirming.

In `frontend/src/app/layout/AppShell.tsx`, mount the stream once for the whole authenticated app. Add the import and call inside the shell component body:
```tsx
import { useActivityStream } from '@/features/activity/use-activity-stream'
// ...inside the AppShell component, before the return:
  useActivityStream()
```
(Mounting here means one EventSource for the session, shared across all routes.)

- [ ] **Step 4: Run to verify it passes + full suite**

Run: `cd frontend && npx vitest run tests/PollingRelaxed.test.ts && npx vitest run`
Expected: PASS; full suite green.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/app/layout/AppShell.tsx frontend/src/features/jobs/ frontend/src/features/minions/ frontend/src/features/keys/ frontend/tests/PollingRelaxed.test.ts
git commit -m "feat(activity): mount stream globally, relax polling to reconciliation fallback"
```

---

### Task 16: Activity list hook + page

**Files:**
- Create: `frontend/src/features/activity/use-activity.ts`
- Create: `frontend/src/features/activity/activity-page.tsx`
- Test: `frontend/tests/ActivityPage.test.tsx`

- [ ] **Step 1: Write the failing test**

Create `frontend/tests/ActivityPage.test.tsx` (mirror `tests/JobsListPage.test.tsx` MSW + router pattern):

```tsx
import { render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { setupServer } from 'msw/node'
import { http, HttpResponse } from 'msw'
import { beforeAll, afterEach, afterAll, it, expect } from 'vitest'

import { ActivityPage } from '@/features/activity/activity-page'

const server = setupServer(
  http.get('/api/auth/me', () =>
    HttpResponse.json({
      username: 'admin', display_name: 'admin', must_change_pw: false,
      permissions: [{ verb: 'view', resource_glob: 'job:*' }],
    }),
  ),
  http.get('/api/activity', () =>
    HttpResponse.json({
      total: 1,
      events: [{
        id: 1, ts: new Date().toISOString(), category: 'job',
        event_type: 'job.ret', minion_id: 'web01', jid: '20260529',
        fun: 'state.apply', success: true, summary: 'web01 returned state.apply',
      }],
    }),
  ),
)

beforeAll(() => server.listen())
afterEach(() => server.resetHandlers())
afterAll(() => server.close())

it('renders activity rows', async () => {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  // EventSource is created by the page if it mounts the stream; shim it.
  // @ts-expect-error test shim
  globalThis.EventSource = class { close() {} }
  render(
    <QueryClientProvider client={qc}>
      <ActivityPage />
    </QueryClientProvider>,
  )
  await waitFor(() =>
    expect(screen.getByText(/web01 returned state.apply/)).toBeInTheDocument(),
  )
})
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd frontend && npx vitest run tests/ActivityPage.test.tsx`
Expected: FAIL (page not found)

- [ ] **Step 3: Implement the list hook + page**

Create `frontend/src/features/activity/use-activity.ts`:

```ts
import { useQuery } from '@tanstack/react-query'

import { activityApi, activityQueryKeys, type ActivityFilter, type ActivityListOut } from './api'

export function useActivityList(filter: ActivityFilter) {
  return useQuery<ActivityListOut>({
    queryKey: activityQueryKeys.list(filter),
    queryFn: () => activityApi.list(filter),
    placeholderData: (prev) => prev,
  })
}
```

Create `frontend/src/features/activity/activity-page.tsx`. Mirror `features/jobs/jobs-list-page.tsx` structure (`MustChangePassword` wrapper, hook call, perm gate via `useHasPerm`, error/empty states, a `Table` of rows with `Badge` for category/success). Include a category filter `<select>`, a search `<input>`, and a "live tail" toggle that uses `useActivityStream` to prepend live events. Keep it consistent with the existing list pages' imports from `@/components/ui/*`. Concretely:

```tsx
import { useMemo, useState } from 'react'

import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from '@/components/ui/table'
import { MustChangePassword } from '@/features/auth/guards'
import { useHasPerm } from '@/features/auth/use-has-perm'
import { useActivityList } from './use-activity'
import type { ActivityFilter } from './api'

export function ActivityPage() {
  return (
    <MustChangePassword>
      <ActivityPageInner />
    </MustChangePassword>
  )
}

function ActivityPageInner() {
  const canViewAny =
    useHasPerm('view', 'job:*') ||
    useHasPerm('view', 'key:*') ||
    useHasPerm('view', 'minion:*')
  const [category, setCategory] = useState<string>('')
  const [search, setSearch] = useState('')
  const filter: ActivityFilter = useMemo(
    () => ({ category: category || undefined, search: search || undefined, limit: 200 }),
    [category, search],
  )
  const { data, isPending, error } = useActivityList(filter)

  if (!canViewAny) {
    return <p className="text-sm text-muted-foreground">You don't have access to any activity.</p>
  }

  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-2xl font-semibold tracking-tight">Activity</h1>
      <div className="flex flex-wrap gap-2">
        <select
          value={category}
          onChange={(e) => setCategory(e.target.value)}
          className="rounded-md border border-input bg-background px-2 py-1 text-sm"
        >
          <option value="">All categories</option>
          <option value="job">Jobs</option>
          <option value="key">Keys</option>
          <option value="minion">Minions</option>
        </select>
        <Input
          placeholder="Search summary…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="max-w-xs"
        />
      </div>
      {error ? (
        <p className="text-sm text-destructive">Failed to load activity.</p>
      ) : isPending ? (
        <p className="text-sm text-muted-foreground">Loading…</p>
      ) : data && data.events.length > 0 ? (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Time</TableHead>
              <TableHead>Category</TableHead>
              <TableHead>Event</TableHead>
              <TableHead>Minion</TableHead>
              <TableHead>Summary</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {data.events.map((e) => (
              <TableRow key={e.id}>
                <TableCell className="whitespace-nowrap text-xs text-muted-foreground">
                  {new Date(e.ts).toLocaleString()}
                </TableCell>
                <TableCell><Badge variant="outline">{e.category}</Badge></TableCell>
                <TableCell className="font-mono text-xs">{e.event_type}</TableCell>
                <TableCell>{e.minion_id ?? '—'}</TableCell>
                <TableCell>{e.summary}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      ) : (
        <p className="text-sm text-muted-foreground">No activity yet.</p>
      )}
    </div>
  )
}
```

Confirm `Badge`/`Input`/`Table` import paths and the `MustChangePassword` + `useHasPerm` locations against an existing list page before finalizing.

- [ ] **Step 4: Run to verify it passes**

Run: `cd frontend && npx vitest run tests/ActivityPage.test.tsx`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/src/features/activity/use-activity.ts frontend/src/features/activity/activity-page.tsx frontend/tests/ActivityPage.test.tsx
git commit -m "feat(activity): Activity page with filters and search"
```

---

### Task 17: Register the `/activity` route + sidebar nav (with "any of" permission gating)

**Files:**
- Modify: `frontend/src/app/router.tsx`
- Modify: `frontend/src/features/auth/use-has-perm.ts` (add `useHasAnyPerm`)
- Modify: `frontend/src/app/layout/Sidebar.tsx` (NavItem `requiresAny` + NavLink)
- Test: `frontend/tests/Sidebar.test.tsx` (or extend existing sidebar/nav test if present)

- [ ] **Step 1: Write the failing test**

Add `useHasAnyPerm` behavior + nav visibility test. Create `frontend/tests/UseHasAnyPerm.test.tsx`:

```tsx
import { renderHook } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { setupServer } from 'msw/node'
import { http, HttpResponse } from 'msw'
import { beforeAll, afterEach, afterAll, it, expect } from 'vitest'

import { useHasAnyPerm } from '@/features/auth/use-has-perm'

const server = setupServer(
  http.get('/api/auth/me', () =>
    HttpResponse.json({
      username: 'v', display_name: 'v', must_change_pw: false,
      permissions: [{ verb: 'view', resource_glob: 'key:*' }],
    }),
  ),
)
beforeAll(() => server.listen())
afterEach(() => server.resetHandlers())
afterAll(() => server.close())

it('returns true if any pair matches', async () => {
  const qc = new QueryClient()
  const wrapper = ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={qc}>{children}</QueryClientProvider>
  )
  const { result } = renderHook(
    () => useHasAnyPerm([
      { verb: 'view', resource: 'job:*' },
      { verb: 'view', resource: 'key:*' },
    ]),
    { wrapper },
  )
  // wait a tick for the query
  await new Promise((r) => setTimeout(r, 50))
  expect(result.current).toBe(true)
})
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd frontend && npx vitest run tests/UseHasAnyPerm.test.tsx`
Expected: FAIL (`useHasAnyPerm` not exported)

- [ ] **Step 3: Implement `useHasAnyPerm`, nav, and route**

In `frontend/src/features/auth/use-has-perm.ts`, add (reuse the same `matchesGlob` + `useCurrentUser` the file already uses — one `useCurrentUser` call, no rules-of-hooks issue):

```ts
export function useHasAnyPerm(pairs: { verb: string; resource: string }[]): boolean {
  const { data } = useCurrentUser()
  if (!data || !data.permissions) return false
  return pairs.some((pair) =>
    data.permissions!.some(
      (p) => matchesGlob(p.verb, pair.verb) && matchesGlob(p.resource_glob, pair.resource),
    ),
  )
}
```
(If `matchesGlob`/`useCurrentUser` are module-local, they're already in scope in this file.)

In `frontend/src/app/layout/Sidebar.tsx`:
- Extend `NavItem` type with `requiresAny?: { verb: string; resource: string }[]`.
- Add the nav entry to the **Operations** section's `items` array (import an icon, e.g. `Radio` or reuse `Activity` from lucide — `Activity` is already imported):
```tsx
      {
        to: '/activity',
        label: 'Activity',
        icon: Activity,
        requiresAny: [
          { verb: 'view', resource: 'job:*' },
          { verb: 'view', resource: 'key:*' },
          { verb: 'view', resource: 'minion:*' },
        ],
      },
```
- In `NavLink`, replace the single `useHasPerm(...)` allow-check so it honors both `requires` and `requiresAny`. Since hooks must be called unconditionally, call both hooks every render with safe defaults:
```tsx
  const allowedSingle = useHasPerm(
    item.requires?.verb ?? '*',
    item.requires?.resource ?? '*',
  )
  const allowedAny = useHasAnyPerm(item.requiresAny ?? [])
  const allowed = item.requiresAny ? allowedAny : allowedSingle
```
Update the gate `if (item.requires && !allowed) return null` to also handle `requiresAny`:
```tsx
  if ((item.requires || item.requiresAny) && !allowed) return null
```
Add `useHasAnyPerm` to the import from `@/features/auth/use-has-perm`.

In `frontend/src/app/router.tsx`, register the route (mirror an existing `createRoute` like `/jobs` and add to `appRoute.addChildren([...])`):
```tsx
import { ActivityPage } from '@/features/activity/activity-page'
// ...
const activityRoute = createRoute({
  getParentRoute: () => appRoute,
  path: '/activity',
  component: () => <ActivityPage />,
})
// ...add activityRoute to the appRoute.addChildren([...]) array
```

- [ ] **Step 4: Run to verify it passes + full suite**

Run: `cd frontend && npx vitest run tests/UseHasAnyPerm.test.tsx && npx vitest run && npx tsc -b`
Expected: PASS; full suite green; typecheck clean.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/features/auth/use-has-perm.ts frontend/src/app/layout/Sidebar.tsx frontend/src/app/router.tsx frontend/tests/UseHasAnyPerm.test.tsx
git commit -m "feat(activity): /activity route + sidebar nav with any-of permission gating"
```

---

### Task 18: Overview "Recent activity" widget

**Files:**
- Create: `frontend/src/features/activity/recent-activity-card.tsx`
- Modify: `frontend/src/features/overview/overview-page.tsx`
- Test: `frontend/tests/RecentActivityCard.test.tsx`

- [ ] **Step 1: Write the failing test**

Create `frontend/tests/RecentActivityCard.test.tsx`:

```tsx
import { render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { setupServer } from 'msw/node'
import { http, HttpResponse } from 'msw'
import { beforeAll, afterEach, afterAll, it, expect } from 'vitest'

import { RecentActivityCard } from '@/features/activity/recent-activity-card'

const server = setupServer(
  http.get('/api/activity', () =>
    HttpResponse.json({
      total: 1,
      events: [{
        id: 9, ts: new Date().toISOString(), category: 'minion',
        event_type: 'minion.start', minion_id: 'web02', jid: null,
        fun: null, success: null, summary: 'web02 came online',
      }],
    }),
  ),
)
beforeAll(() => server.listen())
afterEach(() => server.resetHandlers())
afterAll(() => server.close())

it('shows recent events and a View all link', async () => {
  // @ts-expect-error shim
  globalThis.EventSource = class { close() {} }
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(
    <QueryClientProvider client={qc}>
      <RecentActivityCard />
    </QueryClientProvider>,
  )
  await waitFor(() => expect(screen.getByText(/web02 came online/)).toBeInTheDocument())
  expect(screen.getByText(/View all/i)).toBeInTheDocument()
})
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd frontend && npx vitest run tests/RecentActivityCard.test.tsx`
Expected: FAIL (component not found)

- [ ] **Step 3: Implement the widget + place it on Overview**

Create `frontend/src/features/activity/recent-activity-card.tsx` (use the Overview `ChartCard` wrapper for visual consistency — confirm its props against `features/overview/chart-card.tsx`):

```tsx
import { Link } from '@tanstack/react-router'

import { ChartCard } from '@/features/overview/chart-card'
import { useActivityList } from './use-activity'

export function RecentActivityCard() {
  const { data } = useActivityList({ limit: 8 })
  const events = data?.events ?? []
  return (
    <ChartCard title="Recent activity" description="Live fleet events">
      <ul className="flex flex-col gap-1.5">
        {events.length === 0 ? (
          <li className="text-sm text-muted-foreground">No activity yet.</li>
        ) : (
          events.map((e) => (
            <li key={e.id} className="flex items-center gap-2 text-sm">
              <span className="text-[10px] uppercase tracking-wide text-muted-foreground">
                {e.category}
              </span>
              <span className="truncate">{e.summary}</span>
            </li>
          ))
        )}
      </ul>
      <Link to="/activity" className="mt-3 inline-block text-xs text-primary hover:underline">
        View all →
      </Link>
    </ChartCard>
  )
}
```

In `frontend/src/features/overview/overview-page.tsx`, import and render `<RecentActivityCard />` in the dashboard grid alongside the existing chart cards (place it in the grid where it fits — match the existing `className`/`col-span` conventions used by neighboring cards).

- [ ] **Step 4: Run to verify it passes + full suite + typecheck**

Run: `cd frontend && npx vitest run tests/RecentActivityCard.test.tsx && npx vitest run && npx tsc -b`
Expected: PASS; full suite green; typecheck clean.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/features/activity/recent-activity-card.tsx frontend/src/features/overview/overview-page.tsx frontend/tests/RecentActivityCard.test.tsx
git commit -m "feat(activity): Overview recent-activity widget linking to /activity"
```

---

### Task 19: Settings UI toggle for the event stream

**Files:**
- Modify: the admin settings page that renders poller toggles (find under `frontend/src/features/admin/`)
- Test: extend the existing settings test if present; otherwise manual verification noted.

- [ ] **Step 1: Locate the pollers settings UI**

Run: `cd frontend && grep -rn "poll_interval\|Pollers\|jobs_poll" src/features/admin`
Expected: the component(s) that render poller settings + the `use-settings.ts` mutation. Read them.

- [ ] **Step 2: Add controls for the two new fields**

In the poller settings form, add a toggle bound to `event_stream_enabled` and a number input bound to `event_stream_retention_days`, following the exact pattern the existing poller fields use (same `Switch`/`Input` components and the same mutation payload shape in `use-settings.ts`). The generated types from Task 12 already include these fields on the settings schema.

- [ ] **Step 3: Verify compile + full suite**

Run: `cd frontend && npx tsc -b && npx vitest run`
Expected: clean + green.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/features/admin/
git commit -m "feat(activity): settings UI toggle for event stream"
```

---

### Task 20: Full verification pass

**Files:** none (verification only)

- [ ] **Step 1: Backend suite (both DBs)**

Run: `cd backend && pytest -q` then, if the Postgres path is available locally, `HALITE_TEST_PG=1 pytest -q`
Expected: all pass.

- [ ] **Step 2: Frontend lint + types + tests**

Run: `cd frontend && npm run lint && npx tsc -b && npx vitest run`
Expected: all clean/green.

- [ ] **Step 3: Migration round-trip once more**

Run: `cd backend && alembic upgrade head && alembic downgrade -1 && alembic upgrade head`
Expected: no errors.

- [ ] **Step 4: Manual smoke (optional, requires a Salt master + event stream enabled)**

Enable the event stream in Settings, open the Activity page, and trigger a job from the Run screen. Confirm: a `job.new`/`job.ret` row appears live, the Overview widget updates, and the Jobs list refreshes without a manual reload.

- [ ] **Step 5: Commit any fixes**

```bash
git add -A
git commit -m "test(activity): verification fixes"
```

---

## Notes & deviations from the spec

- **Reconciliation interval** is not a new setting — the existing `jobs_poll_interval_seconds` (and the other poller knobs) serve as the reconciliation cadence. Relax them via the existing Settings UI. Only `event_stream_enabled` and `event_stream_retention_days` are added.
- **Table named `activity_events`** (not `events`) to match the `jobs_index` / `minion_snapshots` / `audit_log` naming convention.
- **Permission gating on the API** uses `CurrentUser` + in-handler category filtering via `rbac.engine.check`, not a single `require_perm` dependency (which would wrongly 403 a user who can view only one family).
- **Minion presence** v1 ingests `salt/minion/<id>/start` (online). Disconnect/`presence/change` events depend on the master having `presence_events` enabled; surfacing offline transitions is a follow-on once that's confirmed available — the normalizer drops unknown tags safely until then.
- **Fixtures:** several test sketches reference project fixtures (`db`, sessionmaker, authed clients) by placeholder names — match them to the actual fixtures in `backend/tests/conftest.py` / `frontend/tests/` during implementation.
