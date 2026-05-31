from __future__ import annotations

import asyncio
import json
from contextlib import contextmanager
from typing import Any


def format_sse(tag: str, data: dict[str, Any]) -> str:
    """Render one Salt SSE frame. Halite reads the tag from the JSON `data:`
    line; we also send a `tag:` line for fidelity with real salt-api."""
    payload = json.dumps({"tag": tag, "data": data})
    return f"tag: {tag}\ndata: {payload}\n\n"


class EventBus:
    """In-process async pub/sub. Publishers call publish(); each subscriber
    gets its own unbounded asyncio.Queue of (tag, data) tuples."""

    def __init__(self) -> None:
        self._subscribers: set[asyncio.Queue] = set()

    @property
    def subscriber_count(self) -> int:
        return len(self._subscribers)

    @contextmanager
    def subscribe(self):
        q: asyncio.Queue = asyncio.Queue()
        self._subscribers.add(q)
        try:
            yield q
        finally:
            self._subscribers.discard(q)

    async def publish(self, tag: str, data: dict[str, Any]) -> None:
        for q in list(self._subscribers):
            q.put_nowait((tag, data))
