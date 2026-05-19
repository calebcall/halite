#!/usr/bin/env sh
set -eu
python3 -c "import secrets; print(secrets.token_urlsafe(48))"
