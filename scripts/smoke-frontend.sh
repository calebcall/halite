#!/usr/bin/env sh
set -eu
cd "$(dirname "$0")/.."

# Self-contained smoke: deliberately exports the variables this run needs so
# we don't depend on the developer's .env. Shell env wins over .env in
# docker compose's interpolation order, so this also overrides a .env that
# might be configured for production (e.g. COOKIE_SECURE=true).
export COOKIE_SECRET="$(scripts/gen-bootstrap-secret.sh)"
export COOKIE_SECURE=false
export BOOTSTRAP_ADMIN_USERNAME=admin
export BOOTSTRAP_ADMIN_PASSWORD=changeme

docker compose -f compose.sqlite.yml up --build -d
trap 'docker compose -f compose.sqlite.yml down' EXIT

# Wait for healthz
for i in $(seq 1 30); do
  if curl -fsS http://localhost:8080/healthz >/dev/null 2>&1; then break; fi
  sleep 1
done

# 1. Browse to / — should serve the SPA
curl -fsS http://localhost:8080/ | grep -qi "halite" || { echo "SPA index missing 'halite'"; exit 1; }

# 2. Hit /api/auth/me without a cookie — should 401
status=$(curl -s -o /dev/null -w '%{http_code}' http://localhost:8080/api/auth/me)
[ "$status" = "401" ] || { echo "unauthenticated /me should be 401, got $status"; exit 1; }

# 3. Log in
curl -fsS -c /tmp/halite-cookies.txt -X POST http://localhost:8080/api/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"admin","password":"changeme"}' >/dev/null

# 4. /me with cookie — should 200
curl -fsS -b /tmp/halite-cookies.txt http://localhost:8080/api/auth/me >/dev/null

echo "Smoke OK."
