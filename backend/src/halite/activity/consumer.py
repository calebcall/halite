from __future__ import annotations

import asyncio
import contextlib
import logging

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from halite.activity.hub import EventHub
from halite.activity.normalize import normalize_event
from halite.activity.service import persist_event, prune_events
from halite.jobs.ingest import upsert_one_job

log = logging.getLogger(__name__)

_BACKOFF_START = 1.0
_BACKOFF_MAX = 30.0


class EventStreamConsumer:
    def __init__(
        self,
        *,
        salt,
        sessionmaker: async_sessionmaker[AsyncSession],
        hub: EventHub,
        retention_days: int,
    ) -> None:
        self._salt = salt
        self._sessionmaker = sessionmaker
        self._hub = hub
        self._retention_days = retention_days
        self._stop = asyncio.Event()
        self._task: asyncio.Task[None] | None = None

    @classmethod
    def from_row(cls, row, *, salt, sessionmaker, hub) -> EventStreamConsumer:
        return cls(
            salt=salt,
            sessionmaker=sessionmaker,
            hub=hub,
            retention_days=row.event_stream_retention_days,
        )

    def start(self) -> None:
        if self._task is None:
            self._task = asyncio.create_task(self._loop(), name="activity-consumer")
            log.info("activity consumer started")

    async def stop(self) -> None:
        self._stop.set()
        if self._task is not None:
            try:
                await asyncio.wait_for(self._task, timeout=10)
            except TimeoutError:
                self._task.cancel()
            self._task = None

    async def _loop(self) -> None:
        backoff = _BACKOFF_START
        while not self._stop.is_set():
            try:
                await self._prune()
                await self._consume_once()
                backoff = _BACKOFF_START
            except Exception:
                log.exception("activity consumer stream error; backing off %.0fs", backoff)
                with contextlib.suppress(TimeoutError):
                    await asyncio.wait_for(self._stop.wait(), timeout=backoff)
                backoff = min(backoff * 2, _BACKOFF_MAX)

    async def _consume_once(self) -> None:
        async for tag, data in self._salt.stream_events():
            if self._stop.is_set():
                return
            ev = normalize_event(tag, data)
            if ev is None:
                continue
            async with self._sessionmaker() as session:
                await persist_event(session, ev)
                if ev["event_type"] == "job.new" and ev["jid"]:
                    try:
                        await upsert_one_job(session, ev["jid"], data)
                    except Exception:
                        log.exception("event-driven job ingest failed for %s", ev["jid"])
                await session.commit()
            self._hub.publish(ev)

    async def _prune(self) -> None:
        try:
            async with self._sessionmaker() as session:
                deleted = await prune_events(session, retention_days=self._retention_days)
                await session.commit()
            if deleted:
                log.info("activity retention prune: %d events removed", deleted)
        except Exception:
            log.exception("activity retention prune failed")
