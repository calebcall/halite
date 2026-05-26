<p align="center">
  <img src="logos/brand/lattice/png/lockup-horizontal-1024.png" alt="halite — Salt operations console" width="480">
</p>

<p align="center">
  <strong>A modern self-hosted web console for SaltStack.</strong><br/>
  Built around the same lattice that gives rock salt its crystalline form.
</p>

<p align="center">
  <a href="#features">Features</a> ·
  <a href="#quick-start-docker">Quick start</a> ·
  <a href="#architecture">Architecture</a> ·
  <a href="#development">Development</a> ·
  <a href="#brand--design">Brand</a> ·
  <a href="#why-halite">Why "halite"?</a>
</p>

---

## Features

Halite covers a SaltStack deployment end-to-end from one console:

- **Overview** — KPIs (online minions, pending keys, running jobs, jobs in 24h) plus three interactive charts (minion-status donut, 24h job-activity area, key-status bar). Server-side bucketing on the activity endpoint scales past the cache's job count. Auto-refreshes every 30s.
- **Minions** — Live status of every connected minion, with grains drilled down on demand.
- **Keys** — Accept, reject, or delete pending minion keys.
- **Jobs** — Browse recent jobs, inspect per-minion results (with highstate parsing), and kill running jobs mid-flight.
- **Run** — Dispatch any Salt execution module function against any target, with full target-type support.
- **Inventory** — 3-level drill-down through installed packages across the fleet (package → versions → installed-on, or minion → packages).
- **Users & Roles** — Permission-driven access. Built-in `admin` / `operator` / `viewer` roles plus arbitrary custom roles, with `verb:resource` permission globs.
- **Audit log** — Every decision the policy engine made, paginated and queryable.
- **About / Colophon** — The brand kit, palette, and project story (in-app at `/about`).

The whole UI is mobile-friendly — the sidebar collapses to a slide-out drawer below `lg`, tables scroll cleanly without breaking iOS back-swipe, touch targets meet HIG minimums.

## Quick start (Docker)

```bash
git clone <this repo>
cd halite

# 1. Copy the env template and generate a real cookie secret.
cp .env.example .env
./scripts/gen-bootstrap-secret.sh
# Paste the secret as the value of COOKIE_SECRET in .env.
# .env.example defaults to COOKIE_SECURE=false for plain-HTTP local testing;
# set it to true in production (HTTPS-fronted deployments).

# 2. For the SQLite (homelab) profile, also flip DATABASE_URL in .env to the
#    sqlite+aiosqlite line that's commented out. The Postgres profile uses
#    the default DATABASE_URL as-is.

# 3. Bring it up.
docker compose -f compose.sqlite.yml up --build    # homelab (SQLite)
# OR
docker compose -f compose.yml up --build           # production-shaped (Postgres)
```

`docker compose` automatically picks values up from `.env` in this directory —
no shell `export`s required.

Browse to **http://localhost:8080/** and sign in as `admin` / `changeme` (the
defaults in `.env.example`; change them in `.env` before first start if you want).

For a non-interactive sanity check:

```bash
curl -s -X POST http://localhost:8080/api/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"admin","password":"changeme"}' -c cookies.txt | jq

curl -s http://localhost:8080/api/auth/me -b cookies.txt | jq
curl -s "http://localhost:8080/api/audit?limit=10" -b cookies.txt | jq
```

## Development

### Backend

```bash
cd backend
python3.13 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
../scripts/dev.sh
```

### Frontend

```bash
# Terminal 1 — backend
cd backend
source .venv/bin/activate
../scripts/dev.sh

# Terminal 2 — frontend
cd frontend
npm install
npm run dev   # opens http://localhost:5173, proxies /api to :8080
```

Regenerate the OpenAPI TypeScript types after backend schema changes:

```bash
./scripts/gen-types.sh
```

### Tests

```bash
# Backend
cd backend
source .venv/bin/activate
pytest -v                   # SQLite only (fast)
HALITE_TEST_PG=1 pytest -v  # also runs Postgres via testcontainers

# Frontend
cd frontend
npm test                    # vitest
npm run build               # tsc + vite — type-check + production build
```

## Architecture

**Backend** (`backend/`)
- FastAPI + Pydantic
- SQLAlchemy 2.x (async) + Alembic migrations
- `asyncpg` (Postgres) and `aiosqlite` (SQLite homelab profile)
- Argon2 password hashing; signed cookie sessions
- Audit log written to the database for every authorization decision
- Talks to `salt-api`'s `rest_cherrypy` endpoint for all Salt interactions; tolerates transient master errors with retries and falls back gracefully when subsystems (e.g. `jobs.active`) are unavailable

**Frontend** (`frontend/`)
- React 19 + TanStack Router (file-based code splits possible but the app is currently a single bundle plus a charts chunk)
- TanStack Query for all server state, with 30-second refresh intervals on long-lived list views
- shadcn/ui primitives on top of Radix + Tailwind CSS
- Recharts for the Overview dashboard, lazy-split into its own chunk
- Vite build pipeline

**Theme & brand**
- CSS custom properties drive light + dark mode (dark by default)
- Single accent color, **Halite Amber `#e5a00d`**, on deep neutrals
- Inter typeface (Rasmus Andersson) for body and the wordmark
- Three mark families in the brand kit (Lattice / Salt Cube / Triple Stack)

## Brand & design

The full design system lives in [`logos/brand/`](logos/brand/):

- `lattice/`, `cube/`, `stack/` — the three icon families, each with horizontal + stacked lockups and a `png/` bundle (16/32/48/192/512/1024/2048)
- `wordmark/` — standalone "halite" wordmark
- `tokens/` — color tokens in both CSS variables and W3C Design Tokens JSON
- `brand-kit.html` — visual showcase (open it in a browser)
- `README.md` — usage guidelines, clear-space rules, minimum sizes

The exploratory work that led to the final marks is preserved under [`logos/concepts/`](logos/concepts/) and [`logos/iterations/`](logos/iterations/).

## Why "halite"?

Halite (/ˈheɪlaɪt/) is the mineralogical name for rock salt — sodium chloride in its natural crystalline form. The mineral grows in perfect cubes, with sodium and chloride ions locked in a regular three-dimensional lattice.

That structure happens to mirror the topology of a SaltStack deployment: a master node at the center, orchestrating a constellation of minions arranged across the network. The same diagram you'd draw for an NaCl unit cell is the diagram you'd draw for a Salt master surrounded by its minions. Both meanings live in the brand's primary mark — the 3×3 amber lattice you see at the top of this README.

The in-app `/about` page goes deeper.

## Project structure

```
halite/
├── backend/                FastAPI app
│   ├── src/halite/         Routes, services, models per feature
│   ├── tests/              pytest suite (unit + integration)
│   └── alembic/            Database migrations
├── frontend/               React SPA
│   └── src/
│       ├── app/            Layout, theme, router
│       ├── features/       One folder per feature area
│       ├── shared/api/     API client + generated OpenAPI types
│       └── components/ui/  shadcn primitives
├── logos/                  Design source
│   ├── concepts/           Exploratory icon concepts
│   ├── iterations/         Iterated design rounds
│   └── brand/              Final brand kit
├── scripts/                Dev shell scripts
├── compose.yml             Production-shaped Docker stack (Postgres)
├── compose.sqlite.yml      Homelab Docker stack (SQLite)
└── Dockerfile
```

## Configuration

See `.env.example` for the full list of env vars (database URL, cookie secret, Salt-API endpoint and service credentials, bootstrap admin user, etc.).

## License

Halite is project-internal infrastructure tooling. Brand marks are project assets — use them for anything Halite-related (app icons, docs, talks, merch), but please not for unrelated projects.
