#!/usr/bin/env sh
set -eu
cd "$(dirname "$0")/../backend"

# create + activate venv if missing
if [ ! -d ".venv" ]; then
  python3.13 -m venv .venv
  . .venv/bin/activate
  pip install --upgrade pip
  pip install -e '.[dev]'
else
  . .venv/bin/activate
fi

export DATABASE_URL="sqlite+aiosqlite:///./halite-dev.db"
export COOKIE_SECRET="$(python3 -c 'import secrets; print(secrets.token_urlsafe(48))')"
export COOKIE_SECURE=false
export BOOTSTRAP_ADMIN_USERNAME=${BOOTSTRAP_ADMIN_USERNAME:-admin}
export BOOTSTRAP_ADMIN_PASSWORD=${BOOTSTRAP_ADMIN_PASSWORD:-changeme}
export LOG_FORMAT=console
alembic upgrade head
exec uvicorn halite.main:create_app --factory --reload --host 127.0.0.1 --port 8080
