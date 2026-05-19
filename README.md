# Halite

Modern self-hosted web UI for managing SaltStack. Green-field replacement for SaltGUI.

Status: Stage 1 in progress (backend foundation).

See [design doc](../SaltGUI/docs/superpowers/specs/2026-05-18-halite-design.md) for the architecture.

## Quick start (dev)

```bash
cd backend
uv sync
./scripts/dev.sh
```

## Tests

```bash
cd backend
uv run pytest -v
```
