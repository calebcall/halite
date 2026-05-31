# mock-salt-api

A standalone server that mimics the salt-api surface Halite consumes
(`POST /login`, `POST /` lowstate dispatch, `GET /events` SSE), backed by a
seeded in-memory fleet with a background simulator. Used for the Halite demo —
see `docs/superpowers/specs/2026-05-31-demo-site-design.md`.

```bash
python3.13 -m venv .venv && . .venv/bin/activate && pip install -e '.[dev]'
pytest -q
uvicorn mock_salt.app:create_app --factory --reload --port 8000
```

Point Halite at it with `SALT_API_URL=http://localhost:8000`, service user
`halite-demo` / `demo` (override via `MOCK_SALT_USERNAME`/`MOCK_SALT_PASSWORD`),
and enable the event stream in Settings.
