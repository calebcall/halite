# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Halite is a self-hosted web console for SaltStack: a FastAPI backend (`backend/`) plus a React 19 SPA (`frontend/`), packaged together into one Docker image that serves the built SPA as static files.

## Commands

### Backend (`backend/`)
```bash
python3.13 -m venv .venv && source .venv/bin/activate && pip install -e '.[dev]'
../scripts/dev.sh          # boots uvicorn on :8080 with a throwaway SQLite db + reload
pytest -v                  # SQLite only (fast)
HALITE_TEST_PG=1 pytest -v # also runs the Postgres leg via testcontainers (CI runs both)
pytest tests/test_rbac_engine.py -v                       # single file
pytest tests/test_rbac_engine.py::test_name -v            # single test
ruff check src tests       # lint (line-length 100, E501 ignored; rules E,F,W,I,B,UP,SIM)
ruff format src tests
alembic upgrade head       # apply migrations
alembic revision -m "msg"  # new migration (files in alembic/versions/, dated prefix)
```

### Frontend (`frontend/`)
```bash
npm install
npm run dev      # vite on :5173, proxies /api -> :8080 (run the backend in another terminal)
npm test         # vitest run
npm run build    # tsc -b && vite build (type-check + production build)
npm run lint     # eslint
```

After changing backend Pydantic schemas, regenerate the frontend's typed API client:
```bash
./scripts/gen-types.sh     # backend must be importable; writes frontend/src/shared/api/types
```

### Docker
```bash
cp .env.example .env && ./scripts/gen-bootstrap-secret.sh   # paste output as COOKIE_SECRET
docker compose -f compose.sqlite.yml up --build   # homelab (SQLite); flip DATABASE_URL in .env first
docker compose -f compose.yml up --build          # production-shaped (Postgres)
```
Default login is `admin` / `changeme` (`BOOTSTRAP_ADMIN_*` in `.env`).

## Architecture

### Two kinds of settings
- **Infra settings** (`config.py`, `Settings`) come from env vars via pydantic-settings: database URL, cookie secret, listen host/port, log config. Read at process start.
- **App settings** (`settings/models.py`, the single `AppSettings` DB row) hold the Salt-API connection (URL, eauth, username, encrypted password) and poller toggles. Editable at runtime through the Settings UI. The salt password is encrypted at rest via `settings/crypto.py`.

### RuntimeConfig is the hub (`runtime.py`)
At boot, `RuntimeConfig` reads the `AppSettings` row and wires up **one** `SaltAPIClient` plus all background schedulers. **If no Salt credentials are stored, `runtime.salt` is `None` and no schedulers start** — every salt-backed endpoint degrades gracefully (503 / empty data) rather than crashing. When the Settings route writes new credentials it calls `runtime.reload(db)`, which tears down and rebuilds the client + schedulers atomically. Routes never hold a salt client reference directly; they fetch the current one via `salt_client_or_503(request)` (`salt/deps.py`) so hot-reloads are transparent.

### Poll-into-DB, serve-from-DB
Salt-API is slow and sometimes unavailable, so most read paths do **not** call Salt live. Background schedulers periodically poll Salt and **ingest** results into snapshot/index tables; routes then query those tables. The recurring per-feature shape is:
- `scheduler.py` — periodic task owned by `RuntimeConfig`
- `ingest.py` — reconciles a snapshot table against fresh Salt data (insert new / update changed / delete vanished)
- `*_model.py` / `snapshot_model.py` / `index_model.py` — the SQLAlchemy snapshot table
- `service.py` + `routes.py` — query the snapshot and serve it

Examples: `minions/` (key + grain snapshots), `fleet/` (fleet ingest + parser), `jobs/` (jobs index + timeline). Live Salt calls are reserved for actions (`run/`, `keys/` accept/reject, killing jobs).

### SaltAPIClient (`salt/client.py`)
Async client for salt-api's `rest_cherrypy`. Single shared `httpx.AsyncClient`, lazy login guarded by an `asyncio.Lock` (N concurrent expired-token requests trigger exactly one re-login), 5xx retried with exponential backoff, 401 retried once after re-login. Helpers: `local_call`, `wheel_call`, `runner_call`, `list_connected_minions`. Raises `SaltAPIError` (non-2xx) / `SaltAPIUnavailable` (network). `wrap_salt_errors()` in `salt/deps.py` translates these into 502/503 HTTPExceptions.

### Auth & RBAC
- Signed-cookie sessions (`itsdangerous`), Argon2 password hashing. `current_user` dependency in `deps.py` resolves the session.
- RBAC is `(verb, resource_glob)` permission pairs attached to roles; a user gets the union across their roles. `rbac/engine.py::check` matches with anchored shell globs (`fnmatch`), `:` as namespace separator (e.g. `key:web-*`). Permissions are preloaded onto `user.permissions_cache`.
- Guard routes with `require_perm(verb, resource)` (dependency factory in `deps.py`) → 403 on miss.
- **Every authorization decision is written to the audit log** (`audit/writer.py`), queryable at `/api/audit`.

### App entry point
`main.py::create_app` is a **factory** — there is intentionally no module-level `app` (importing it would force env-var reads at import time and break tests). Uvicorn launches it via `--factory`. The lifespan handler seeds builtin roles, bootstraps the admin user, then boots `RuntimeConfig`. When `settings.static_dir` is set, the SPA build is mounted and a catch-all serves `index.html` for client-side routing (real files like the touch icon are served first).

### Database portability
The app runs on both Postgres (`asyncpg`) and SQLite (`aiosqlite`), so queries must work on both. Avoid PG-only operators/types; route portability concerns through `db_dialect.py` (e.g. `lower_eq` for case-insensitive matching against pre-lowercased columns like `username_lower`). The pytest suite enforces this by running every DB test against both backends.

### Frontend layout (`frontend/src/`)
- `app/` — layout, theme (CSS-variable light/dark, dark default, single accent **Halite Amber `#e5a00d`**), TanStack Router setup
- `features/<area>/` — one folder per feature (overview, minions, keys, jobs, run, inventory, users, roles, audit, fleet, …), mirroring the backend modules
- `shared/api/` — API client + **generated** OpenAPI TS types (do not hand-edit; regenerate via `gen-types.sh`)
- `components/ui/` — shadcn/ui primitives (Radix + Tailwind)
- TanStack Query for all server state; long-lived list views auto-refresh every 30s. Recharts (Overview) is lazy-split into its own chunk.

## Conventions
- Backend feature modules are self-contained: `routes.py` / `service.py` / `schemas.py` / `models.py` (+ `ingest.py` / `scheduler.py` where there's a snapshot). Keep new features in that shape.
- `from __future__ import annotations` at the top of backend modules.
- Tests live in `backend/tests/` as `test_<feature>_<layer>.py`; `conftest.py` provides the dual-backend DB fixtures (migrations run from a sync context because alembic's `env.py` uses `asyncio.run()` internally).
- New migrations go in `backend/alembic/versions/` with a `YYYYMMDD_NNNN_description` filename.
