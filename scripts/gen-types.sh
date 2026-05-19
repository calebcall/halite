#!/usr/bin/env sh
set -eu

# Generate frontend TS types from the backend's live OpenAPI schema.
# Runs the backend just long enough to grab the spec.

cd "$(dirname "$0")/.."

# Bring the backend up against a throwaway sqlite DB so its lifespan doesn't
# need real config.
SPEC_DB="$(mktemp -t halite-openapi.XXXXXX)"
trap 'rm -f "$SPEC_DB"' EXIT

cd backend
. .venv/bin/activate

DATABASE_URL="sqlite+aiosqlite:///$SPEC_DB" \
COOKIE_SECRET="$(python3 -c 'import secrets; print(secrets.token_urlsafe(48))')" \
COOKIE_SECURE=false \
python -c "
import json
from halite.config import Settings
from halite.auth.cookies import CookieCodec
from halite.main import create_app

settings = Settings()
app = create_app(settings=settings, codec=CookieCodec(settings.cookie_secret))
print(json.dumps(app.openapi()))
" > "/tmp/halite-openapi.json"

cd ../frontend
npx openapi-typescript /tmp/halite-openapi.json -o src/shared/api/types.gen.ts
