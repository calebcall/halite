# backend/src/halite/salt_docs/service.py
from __future__ import annotations

import asyncio
import time
from datetime import UTC, datetime

from halite.salt.client import SaltAPIClient

# Module-level cache. Survives across requests but resets on container
# restart, which is acceptable — a 1-hour TTL bounds the salt-api blast
# radius even if a salt module is dynamically loaded mid-cache.
_CACHE_TTL_S = 3600.0
_cache: dict[str, object] = {}
_cache_lock = asyncio.Lock()


async def get_functions(client: SaltAPIClient) -> tuple[list[str], datetime]:
    """Return (functions, cached_at). Coalesces concurrent cache misses
    under an asyncio.Lock so N parallel callers produce 1 upstream call."""
    now = time.time()
    functions = _cache.get("functions")
    cached_at_ts = _cache.get("cached_at_ts")
    if (
        isinstance(functions, list)
        and isinstance(cached_at_ts, float)
        and now - cached_at_ts < _CACHE_TTL_S
    ):
        return functions, datetime.fromtimestamp(cached_at_ts, tz=UTC)

    async with _cache_lock:
        # Re-check after acquiring the lock — another waiter may have refreshed.
        functions = _cache.get("functions")
        cached_at_ts = _cache.get("cached_at_ts")
        now = time.time()
        if (
            isinstance(functions, list)
            and isinstance(cached_at_ts, float)
            and now - cached_at_ts < _CACHE_TTL_S
        ):
            return functions, datetime.fromtimestamp(cached_at_ts, tz=UTC)

        fetched = await client.list_execution_functions()
        cached_at_ts = time.time()
        _cache["functions"] = fetched
        _cache["cached_at_ts"] = cached_at_ts
        return fetched, datetime.fromtimestamp(cached_at_ts, tz=UTC)


def _reset_cache_for_tests() -> None:
    """Test-only: clear the module cache so tests start fresh."""
    _cache.clear()
