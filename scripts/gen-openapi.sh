#!/usr/bin/env sh
set -eu

# Generate docs/api/openapi.json from the backend's live OpenAPI schema, then
# inject x-mint metadata to disable the interactive playground (Halite is
# self-hosted; there is no public server to call). Mirrors scripts/gen-types.sh.

cd "$(dirname "$0")/.."

SPEC_DB="$(mktemp -t halite-openapi.XXXXXX)"
trap 'rm -f "$SPEC_DB"' EXIT

cd backend
if [ ! -d ".venv" ]; then
  python3.13 -m venv .venv
  . .venv/bin/activate
  pip install --upgrade pip
  pip install -e '.[dev]'
else
  . .venv/bin/activate
fi

DATABASE_URL="sqlite+aiosqlite:///$SPEC_DB" \
COOKIE_SECRET="$(python3 -c 'import secrets; print(secrets.token_urlsafe(48))')" \
COOKIE_SECURE=false \
PYTHONPATH=src \
python -c "
import json
from halite.config import Settings
from halite.auth.cookies import CookieCodec
from halite.main import create_app

settings = Settings()
app = create_app(settings=settings, codec=CookieCodec(settings.cookie_secret))
spec = app.openapi()
# Disable Mintlify's interactive playground (no public server to call);
# request/response examples still render.
spec['x-mint'] = {'metadata': {'playground': 'none'}}
print(json.dumps(spec, indent=2))
" > ../docs/api/openapi.json

echo "Wrote docs/api/openapi.json"
