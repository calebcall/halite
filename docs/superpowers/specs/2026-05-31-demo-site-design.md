# Halite Demo Site — Design

**Date:** 2026-05-31
**Status:** Approved (pending spec review)

## Goal

Stand up a public, self-contained demo of Halite that needs no real Salt master and cannot be vandalized. Two components:

1. A **mock salt-api service** — a standalone server that faithfully mimics the salt-api surface Halite consumes (login, the lowstate `POST /` dispatcher, and the `GET /events` SSE bus), backed by a believable, mutable in-memory fleet. A background simulator keeps the event stream alive; visitor actions mutate state and emit matching events.
2. A Halite **demo mode** — a flag that auto-logs visitors in as a broad-view demo user and hard-blocks the sensitive edits (users, RBAC, settings), while leaving Salt actions (Run, key accept/reject/delete, kill job) interactive against the mock.

Plus the deployment glue (`compose.demo.yml` + seed) to run the two together.

## Decisions (from brainstorming)

| Decision | Choice |
|---|---|
| Mock fidelity | Stateful, fully interactive — visitors Run commands, accept/reject/delete keys, kill jobs; state mutates and emits events |
| Events | Mock emits `/events` SSE matching the consumer contract (`activity/normalize.py`) |
| Liveness | Background fleet simulator emits a continuous, believable event stream; resets to baseline on a timer |
| Demo sign-in | Auto-login as a `demo` user (broad `view` + salt actions); blocked from users/RBAC/settings edits |
| Halite demo DB | Ephemeral SQLite — container restart resets it |
| Deployment | `compose.demo.yml` + boot-time seed; hosting is out of scope (maintainer deploys) |

## Non-goals (v1)

- No CI / hosting / TLS config — just the compose profile and seed.
- No per-visitor isolation — the mock fleet is shared across concurrent visitors, with periodic reset. (Per-session state is a possible future enhancement.)
- No persona switcher (viewer/operator/admin) — single broad-view demo user. (Future enhancement.)
- No changes to Halite's real polling/event architecture — Halite runs unmodified except the demo-mode additions.
- The mock does not implement salt-api surfaces Halite never calls (beacons, the REST `/minions` `/jobs` GET routes, `event.send`, etc.).

## Consumed contract (what the mock must satisfy)

Verified against the merged event-stream refactor. Halite's `SaltAPIClient` only hits:

**`POST /login`** → `{return: [{token, expire, start, user, eauth, perms}]}`. `token` is treated as a session id; subsequent calls send `X-Auth-Token`.

**`POST /`** (lowstate dispatch; body is `[{client, fun, ...}]`, header `X-Auth-Token`):

| client | fun | Used by | Return shape |
|---|---|---|---|
| wheel | `key.list_all` | minion/key ingest | `{return:[{data:{return:{minions, minions_pre, minions_rejected, minions_denied, local}}}]}` |
| wheel | `key.accept` / `key.reject` / `key.delete` | Keys actions | wheel ack shape |
| runner | `manage.present` (±`show_ip`) | presence | list of ids, or list of `[id, ip]` |
| runner | `cache.grains` (`tgt`, `tgt_type=list`) | grains refresh | `{return:[{minion: grains, …}]}` |
| runner | `jobs.list_jobs` | jobs ingest/backfill | `{return:[{jid: {Function, Target, Target-type, User, StartTime, Arguments}, …}]}` |
| runner | `jobs.list_job` (`jid`) | job detail | `{return:[{jid, Function, Result:{minion:{return,retcode,…}}, …}]}` |
| runner | `jobs.active` | running jobs | `{return:[{jid: {…}}]}` |
| runner | `saltutil.kill_job` (`jid`) | kill | ack |
| local | `grains.items` / `grains.item` | minion grains | `{return:[{minion: {…}}]}` |
| local | `sys.list_functions` (`tgt=*`) | Run autocomplete | `{return:[{minion: [fun, …]}]}` |
| local_async | arbitrary `fun` (`tgt`, `tgt_type`, `arg`, `kwarg`) | Run | `{return:[{jid, minions:[…]}]}` |

**`GET /events`** (SSE; auth via `?token=` query param; `Accept: text/event-stream`). Frames are `data: {json}` lines terminated by a blank line; the JSON is `{"tag": "...", "data": {...}}`. The mock should also send the `tag:` line for fidelity, but Halite reads the tag from the JSON.

**Event tags/shapes the normalizer consumes** (everything else is ignored, so the mock only needs these):

- `salt/job/<20-digit-jid>/new` — `data: {fun, minions:[…], user, tgt}`
- `salt/job/<jid>/ret/<minion>` — `data: {id, fun, retcode, return, user, tgt}` (success = `retcode == 0`; "changed"/duration derived from a state-style `return` dict keyed by state-id with `changes`/`duration`)
- `salt/minion/<minion>/start` — minion came online
- `salt/key` **or** `salt/auth` — `data: {id, act}` where `act ∈ {accept, reject, delete, pend}`

JIDs are 20-digit `YYYYMMDDHHMMSSffffff` timestamps.

## Component 1 — mock-salt-api service

New standalone FastAPI app at `mock-salt-api/` (own `pyproject.toml`, `Dockerfile`, tests). Files, each one responsibility:

- `fleet.py` — the in-memory `Fleet` model + deterministic seed (fixed RNG seed). Holds minions (id, grains, online/present, key-state), jobs (jid → metadata + per-minion returns), highstate/compliance runs, package inventory. Pure data + mutation methods (`accept_key`, `reject_key`, `delete_key`, `dispatch_job`, `complete_job`, `kill_job`, `minion_start`). Mutations return the event(s) to emit.
- `dispatch.py` — the lowstate dispatcher: maps `(client, fun)` → a function that reads/mutates `Fleet` and returns the salt-api-shaped body. Unknown `(client, fun)` returns an empty-but-valid shape (never 500).
- `events.py` — an async pub/sub `EventBus` (asyncio.Queue per subscriber) + SSE formatter. `publish(tag, data)` fans out.
- `simulator.py` — background task: every few seconds dispatch a synthetic job (`job/new` → staggered `job/ret/<minion>` with believable returns, occasional failures), and occasionally emit a `minion/start` or a `key/pend`. Drives liveness with zero visitor input.
- `reset.py` — re-seeds the `Fleet` to baseline on a configurable interval (`MOCK_RESET_MINUTES`, default 30) so the shared demo stays clean.
- `app.py` — FastAPI wiring: `POST /login`, `POST /` (→ `dispatch`), `GET /events` (StreamingResponse from `EventBus`), lifespan starts simulator + reset loop. Config via env (`MOCK_SALT_USERNAME`, `MOCK_SALT_PASSWORD`, `MOCK_RESET_MINUTES`, fleet size).

### Seeded fleet (baseline)
- **~40 minions**, mixed OS grains: Ubuntu 22.04/24.04, Debian 12, Rocky/Alma 9, Alpine 3.x, 2× Windows Server 2022; role grains (`web`/`db`/`cache`/`edge`) and realistic `fqdn`, `ip4_interfaces`, `osrelease`, etc.
- **Keys:** ~35 accepted, 3 pending, 1 rejected, 1 denied (so Keys has actionable items).
- **Presence:** most online; a few offline; a couple stale (last-seen > 2 days) to exercise Fleet Health's `stale` status.
- **Jobs:** ~250 over the last 24–48h (`test.ping`, `state.apply`, `pkg.install`, `cmd.run`, `service.restart`) with per-minion returns including some failures and some "changed" state returns.
- **Highstate/compliance:** recent `state.apply`/`state.highstate` runs across the fleet with a handful of `unhealthy`/`changed`/`stale` minions so Fleet Health and the compliance trend are non-trivial.
- **Inventory:** packages across minions with deliberate version variance for the 3-level drill-down + version compare.

### Interactivity (events emitted on action)
- Run (`local_async`) → assign jid, return `{jid, minions}`, emit `job/new` then staggered `job/ret/<minion>` (results synthesized from the requested `fun`).
- `key.accept`/`reject`/`delete` → mutate key-state, emit `salt/key` with matching `act` (and `minion/start` shortly after an accept, to mimic a minion coming online).
- `saltutil.kill_job` → mark the active job killed, emit terminal returns.

## Component 2 — Halite demo mode

Flag `HALITE_DEMO_MODE` (new `Settings` field in `config.py`, default `false`). When true:

- **Write lockdown** — a middleware (`demo.py`) that, for mutating methods (`POST/PUT/PATCH/DELETE`), returns `403 {"detail": "This action is disabled in the demo."}` for paths under `/api/users`, `/api/roles`, `/api/admin/settings`, **and** the credential-mutating auth routes (`/api/auth/change-password` and any password-reset route — otherwise a visitor could change the shared demo user's password and lock everyone out). Salt-action paths (`/api/run`, `/api/keys`, `/api/jobs/*/kill`), the session routes (`/api/auth/login`, `/api/auth/demo-login`, `/api/auth/logout`, `/api/auth/me`), and template create/update/delete (ephemeral, reset with the DB) are explicitly **allowed**. Central allow/deny prefix lists; everything not in the deny list is allowed.
- **Demo seed** (extends the lifespan seed, demo-mode only) — idempotently create:
  - a `demo` role: `view` on every resource family (`minion:*`, `key:*`, `job:*`, `grain:*`, `pillar:*`, `event:*`, `setting:*`, `inventory:*`, `user:*`, `role:*`, `audit:*`) plus `execute salt:*`, `accept/reject/delete key:*`, `kill job:*` — but **not** `manage_user`, `manage_role`, or `edit settings:*`.
  - a `demo` user (active, `must_change_pw=false`) bound to that role.
  - `AppSettings` configured for the mock: `salt_api_url=$SALT_API_URL`, service username/password, `event_stream_enabled=true`, and non-zero `fleet_poll_interval_seconds` / `jobs_poll_interval_seconds` (e.g. 60) so both the reconciliation pollers and the live stream populate the UI.
- **Demo login** — `POST /api/auth/demo-login`, enabled only in demo mode, issues the `demo` user's signed session cookie (no password). 404/disabled otherwise.
- **Public config** — `GET /api/config` (unauthenticated) returns `{"demo": true|false}` so the SPA can adapt.
- **Frontend** — on load, read `/api/config`; in demo mode: auto-call `demo-login` then route into the app, render a persistent **"Demo mode — read-only"** banner, and hide/disable the locked write controls (user/role/settings editors). The backend 403 remains the hard guarantee; the UI hiding is cosmetic.

## Deployment — `compose.demo.yml`

- `mock-salt-api` — built from `mock-salt-api/Dockerfile`; exposes its port on the demo network only.
- `app` — the Halite image with `HALITE_DEMO_MODE=1`, `SALT_API_URL=http://mock-salt-api:8000`, a generated `COOKIE_SECRET`, `COOKIE_SECURE` per the hosting front (documented), and ephemeral SQLite (named volume optional; default ephemeral so restart = clean). Demo seed runs in the existing lifespan.
- Mock self-resets on its timer; Halite DB resets on container restart. No external DB.

## Phasing (two implementation plans)

1. **Phase 1 — mock-salt-api service.** Build the service + tests. Verifiable independently: run it, point a local Halite (`SALT_API_URL`, event stream enabled) at it, confirm the Activity feed streams and Minions/Keys/Jobs/Run/Inventory/Fleet pages populate and react to actions.
2. **Phase 2 — demo mode + compose.** `HALITE_DEMO_MODE`, lockdown middleware, demo seed, `demo-login`, `/api/config`, frontend banner/auto-login/disable, `compose.demo.yml`.

## Testing

- **Mock:** unit tests per `(client, fun)` → asserted return shape; an events-contract test that feeds each emitted `(tag, data)` through a copy of (or import of) `activity/normalize.py`'s expectations and asserts it normalizes to the intended `category/event_type/...`; a test that an action (accept key / run) mutates fleet state and publishes the right event.
- **Demo mode (Halite):** in demo mode, `POST/PATCH/DELETE` on users/roles/settings → 403; `/api/run`, `/api/keys/*`, `/api/jobs/*/kill` → not blocked; `demo-login` issues a session that `auth/me` accepts; `/api/config` reports `demo:true`. With demo mode off, `demo-login` is unavailable and lockdown is inert.

## Open risks / notes

- **Shared mutable state:** concurrent visitors share one fleet; one visitor's accept/run is visible to others until reset. Acceptable for a demo; documented. Periodic reset bounds drift.
- **Single-worker constraint:** the real `EventHub` already assumes a single uvicorn worker; the demo inherits that (fine — one worker).
- **Event-shape drift:** if `activity/normalize.py` changes which tags/shapes it accepts, the mock's emitted events must track it — the events-contract test is the guard. Re-run after pulling Halite changes.
- **`/api/config` route ordering:** Halite already mounts a catch-all SPA route; ensure `/api/config` (and `demo-login`) register before the catch-all (they're under `/api`, which is matched first — verify).
