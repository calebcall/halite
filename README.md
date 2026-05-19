# Halite

Modern self-hosted web UI for managing SaltStack. Green-field replacement for SaltGUI.

**Status: Stage 1 backend foundation complete.** This release provides:

- `POST /api/auth/login` / `POST /api/auth/logout` / `GET /api/auth/me`
- `GET /api/audit` with column filters and pagination
- `GET /healthz` and `GET /readyz`
- Bootstrap admin via env vars on first start
- Three built-in roles (admin / operator / viewer)

The frontend and salt-facing feature pages arrive in later plans.

## Quick start (Docker)

```bash
git clone <this repo>
cd halite

# Generate a cookie secret
export COOKIE_SECRET="$(./scripts/gen-bootstrap-secret.sh)"
export BOOTSTRAP_ADMIN_USERNAME=admin
export BOOTSTRAP_ADMIN_PASSWORD=changeme

# Homelab (SQLite)
docker compose -f compose.sqlite.yml up --build

# Shared / production (Postgres)
docker compose -f compose.yml up --build
```

Then:

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
