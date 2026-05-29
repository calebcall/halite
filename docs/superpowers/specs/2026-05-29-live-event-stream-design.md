# Live Event Stream — Design

**Date:** 2026-05-29
**Status:** Approved (pending spec review)
**Feature:** #1 of a two-part sequence. Feature #2 (config-drift / compliance) builds on the `events` substrate defined here and gets its own spec.

## Summary

Halite is currently a polling console: background schedulers poll salt-api and
persist into the DB (`jobs_index`, fleet, minion stores), and the frontend
re-fetches that persisted data on a 30s timer. This feature subscribes to
Salt's **event bus** and turns Halite real-time on both ends:

1. A **durable, searchable activity feed** of live fleet events (jobs, key
   activity, minion presence) — a dedicated **Activity page** plus a compact
   **Overview widget** that deep-links into it.
2. **Event-driven freshness** across the existing app: relevant events
   invalidate the matching client queries, so Jobs / Minions / Keys / Overview
   update the instant something happens instead of on a timer.

Both ride one shared stream — built once, both benefits.

## Goals

- Subscribe to salt-api's `/events` SSE endpoint server-side via a single
  long-lived connection, normalize events, and fan them out to browsers.
- Persist a durable event log (`events` table) that survives restarts and is
  searchable/filterable.
- Make event ingestion event-driven (real-time updates to `jobs_index` etc.),
  with the existing schedulers relaxed to a reconciliation safety-net.
- Replace timer-based UI refresh with event-driven query invalidation.
- Respect existing RBAC: a user only sees events for resource families they can
  already `view`.

## Non-goals (v1)

- Beacon and custom (`event.send`) events — ingest only jobs / keys / minions.
- Global slide-over drawer placement (option B from brainstorming) — Activity
  page + Overview widget only.
- Multi-worker deployment of the event hub — documented single-worker
  constraint (see Constraints).
- Config-drift / compliance detection — that is feature #2.

## Decisions (from brainstorming)

| Decision | Choice |
|---|---|
| Scope | Both: live feed **and** real-time refresh of existing screens, one shared system |
| Event families (v1) | Jobs (new + returns), Key activity, Minion presence |
| Event log persistence | Durable `events` table (not just in-memory) — also seeds feature #2 |
| Transport | **SSE** (one-way, rides cookie session, `EventSource` auto-reconnect) |
| Feed placement | **A + C**: dedicated Activity page (full/searchable) + Overview widget that links into it |
| Permission model | Filter per existing permission — events inherit their family's `view` gate |

## Architecture

```
salt-api /events (SSE)  ──▶  EventConsumer (1 bg task)  ──▶  EventHub (in-proc pub/sub + ring buffer)
                                      │                              │
                                      ▼                              ▼
                            event-driven ingest          per-client SSE fan-out
                            (jobs_index, minion store,    (/api/activity/stream)
                             durable events table)         filtered by permission
                                      ▲
                            slow reconciliation poll (existing schedulers, relaxed interval)
```

Browsers never connect to Salt. The backend is the single point of contact with
the bus and the only writer to the durable log.

### Components

**`salt/events.py` — upstream consumer.** In-process background task with the
same lifecycle as the existing schedulers (started in the app lifespan, stopped
on shutdown). Holds one long-lived SSE connection to salt-api's `/events` using
the service-account token; reconnects with exponential backoff on drop; refreshes
the token on 401 (reusing `SaltAPIClient`'s token handling).

**`events/` module — durable log + hub.**
- `EventHub`: in-memory async pub/sub. The consumer publishes normalized events;
  browser SSE connections subscribe. Maintains a small in-memory **ring buffer**
  (recent events) so a newly connected client gets immediate context before the
  durable-table query is even needed for the live tail.
- Normalizer: raw Salt tag/data → typed row (`category`, `event_type`,
  `minion_id`, `jid`, `fun`, `success`, `summary`, `raw`, `ts`).
- Persists each normalized event to the `events` table.

**Event-driven ingest.** On `salt/job/<jid>/ret/<minion>`, the consumer triggers
ingest of that job into `jobs_index` immediately (reusing `jobs/ingest.py`
logic). Key and minion events update their respective stores. The persisted
tables that historical features read stay fresh in real-time.

**Reconciliation safety-net.** The existing `JobsIndexScheduler` (and fleet /
minion schedulers) remain, but their intervals relax (configurable) and they
become backfill — catching anything missed while the SSE connection was down.
Live path = stream; correctness floor = poll.

**`/api/activity/stream` — downstream SSE.** Browser connects with its cookie
session. On connect: replay the recent ring buffer, then stream live.
**Per-connection permission filtering**: the user's perms are evaluated once at
connect, and only event categories they can `view` are forwarded.

**`/api/activity` — REST.** Paginated, filterable, searchable reads from the
`events` table for the Activity page (also permission-filtered).

## Data model — `events` table (new + Alembic migration)

| column | type | notes |
|---|---|---|
| `id` | pk | |
| `ts` | datetime (UTC) | indexed; event time |
| `category` | str | `job` · `key` · `minion` — drives the permission filter |
| `event_type` | str | `job.new`, `job.ret`, `key.pend`, `key.accept`, `key.reject`, `minion.start`, `minion.disconnect` |
| `minion_id` | str, null | indexed |
| `jid` | str, null | indexed (links to Jobs) |
| `fun` | str, null | salt function (job events) |
| `success` | bool, null | job return outcome |
| `summary` | str | human one-liner shown in the feed |
| `raw` | json | full payload, for the detail drawer |

Indexes: `(ts desc)`, `(category, ts)`, `(minion_id, ts)`, `(jid)`.

### Category → permission map

| category | required permission |
|---|---|
| `job` | `view job:*` |
| `key` | `view key:*` |
| `minion` | `view minion:*` |

## Frontend

**`useActivityStream` hook** — wraps `EventSource` on `/api/activity/stream`.
Surfaces connection state (connecting / live / reconnecting). Two
responsibilities: push events into the feed UI, and fire query invalidation.

**Invalidation map** (makes the existing app live):

| event | invalidates |
|---|---|
| `job.*` | jobs list, jobs timeline, minion-runs, Overview KPIs + activity chart |
| `key.*` | keys list, Overview key-status bar |
| `minion.*` | minions list, Overview status donut |

The hard-coded `refetchInterval: 30_000` polls relax to a long fallback
(~5 min). Live freshness comes from invalidation; the slow poll is the safety
net (mirrors the backend belt-and-suspenders).

**Activity page (`/activity`)** — new sidebar item under **Operations**. Visible
if the user has any of `view job:*` / `view key:*` / `view minion:*`.
Virtualized feed reading `/api/activity`, with filters (category, minion, type,
time range, success) + search, and a **live-tail toggle** that prepends streamed
events. Clicking a row opens a detail drawer rendering `raw`.

**Overview widget** — compact "Recent activity" card (last ~8 events, live) with
a **"View all →"** deep-link into `/activity`.

## Settings

Three knobs alongside the existing per-poller toggles:
- Event stream enable / disable.
- Reconciliation interval (the relaxed scheduler cadence).
- Event retention in days (default **30**).

## Retention

A small periodic prune deletes `events` rows older than the configured retention
window, so the table does not grow unbounded.

## Constraints

- **Single-worker.** The Dockerfile runs one uvicorn process (no `--workers`),
  so in-process pub/sub + ring buffer is correct. Scaling to multiple workers
  would require a shared broker (e.g. Redis pub/sub); explicitly out of scope and
  documented as a v1 constraint.
- **At-least-once / gaps.** During an SSE disconnect, live events may be missed;
  the reconciliation poll backfills `jobs_index`. The durable `events` log is
  best-effort for the missed window (acceptable for an activity feed).

## Testing

**Backend (pytest):**
- Normalizer: raw Salt tag/data → typed row, per event type.
- Per-connection permission filter (viewer with only `job:*` sees job events,
  not key/minion).
- `EventHub` pub/sub + ring buffer behavior.
- Consumer reconnect/backoff against a fake SSE source; token refresh on 401.
- Retention prune.
- Integration: `/api/activity/stream` replays buffer then streams live,
  filtered by the connecting user's perms; `/api/activity` REST filtering.
- Reuses the existing injectable salt-client transport pattern.

**Frontend (vitest + MSW):**
- `useActivityStream` against a mocked `EventSource` (events → invalidation).
- Invalidation wiring per category.
- Activity page filters / search / live-tail.
- Overview widget rendering + deep-link.

## Build sequence (high level)

1. `events` table + migration; normalizer; `EventHub`.
2. `salt/events.py` consumer + lifespan wiring; reconnect/backoff.
3. Event-driven ingest into `jobs_index` / stores; relax scheduler intervals.
4. `/api/activity/stream` (SSE, permission-filtered) + `/api/activity` REST.
5. Retention prune + Settings knobs.
6. `useActivityStream` hook + invalidation map; relax `refetchInterval`s.
7. Activity page (nav, feed, filters, search, detail drawer).
8. Overview widget + deep-link.
9. Tests throughout (backend + frontend).
