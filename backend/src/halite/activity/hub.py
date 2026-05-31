from __future__ import annotations

import asyncio
import logging
from collections import deque
from typing import Any

log = logging.getLogger(__name__)

Event = dict[str, Any]
_QUEUE_MAXSIZE = 1000


class EventHub:
    """In-process pub/sub for normalized events plus a bounded ring buffer
    of recent events for replay-on-connect. Single-worker only (see spec)."""

    def __init__(self, ring_size: int = 500) -> None:
        self._subscribers: set[asyncio.Queue[Event]] = set()
        self._ring: deque[Event] = deque(maxlen=ring_size)

    def publish(self, event: Event) -> None:
        self._ring.append(event)
        for q in list(self._subscribers):
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                log.warning("activity subscriber queue full; dropping event")

    def subscribe(self) -> asyncio.Queue[Event]:
        q: asyncio.Queue[Event] = asyncio.Queue(maxsize=_QUEUE_MAXSIZE)
        self._subscribers.add(q)
        return q

    def unsubscribe(self, q: asyncio.Queue[Event]) -> None:
        self._subscribers.discard(q)

    def recent(self) -> list[Event]:
        return list(self._ring)
