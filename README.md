# Halite

Modern self-hosted web UI for managing SaltStack. Green-field replacement for SaltGUI.

**Status: Stage 1 backend foundation + users/roles admin + frontend foundation complete.** This release provides:

- Full backend REST surface for auth, users, roles, permissions, audit, health
- React SPA login + app shell, served by FastAPI when `HALITE_STATIC_DIR` is set
- Bootstrap admin via env vars on first start
- Three built-in roles (admin / operator / viewer)

The salt-facing feature pages arrive in later plans.

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
defaults in `.env.example`; change them in `.env` if you want).

For a non-interactive sanity check:

```bash
curl -s -X POST http://localhost:8080/api/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"admin","password":"changeme"}' -c cookies.txt | jq

curl -s http://localhost:8080/api/auth/me -b cookies.txt | jq

curl -s "http://localhost:8080/api/audit?limit=10" -b cookies.txt | jq
```

## Local dev

```bash
cd backend
python3.13 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
../scripts/dev.sh
```

## Frontend dev

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

To regenerate the OpenAPI TypeScript types after backend schema changes:

```bash
./scripts/gen-types.sh
```

## Tests

```bash
cd backend
source .venv/bin/activate
pytest -v                  # SQLite only (fast)
HALITE_TEST_PG=1 pytest -v # also runs Postgres via testcontainers
```

## Configuration

See `.env.example` for the full list of env vars.

## Architecture

See `../SaltGUI/docs/superpowers/specs/2026-05-18-halite-design.md` (in the sibling SaltGUI checkout) for the design.
