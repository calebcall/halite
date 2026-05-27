from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from halite.jobs.ingest import refresh_active_jids, refresh_jobs_index
from halite.salt.client import SaltAPIClient

if TYPE_CHECKING:
    pass

log = logging.getLogger(__name__)


class JobsIndexScheduler:
    """Single-loop scheduler. Per tick it refreshes jobs_index from
    ``runner.jobs.list_jobs`` and then pushes a fresh active-jids set
    into the supplied callback (used by RuntimeConfig to populate its
    in-memory cache).
    """

    def __init__(
        self,
        interval_seconds: int,
        initial_delay_seconds: int,
        salt: SaltAPIClient,
        sessionmaker: async_sessionmaker[AsyncSession],
        on_active_refresh: Callable[[set[str], datetime], None],
    ) -> None:
        self._interval_seconds = interval_seconds
        self._initial_delay_seconds = initial_delay_seconds
        self._salt = salt
        self._sessionmaker = sessionmaker
        self._on_active_refresh = on_active_refresh
        self._stop = asyncio.Event()
        self._task: asyncio.Task[None] | None = None

    @classmethod
    def from_row(
        cls,
        row: Any,  # noqa: ANN401  — duck-typed AppSettings row
        *,
        salt: SaltAPIClient,
        sessionmaker: async_sessionmaker[AsyncSession],
        on_active_refresh: Callable[[set[str], datetime], None],
    ) -> JobsIndexScheduler:
        return cls(
            interval_seconds=row.jobs_poll_interval_seconds,
            initial_delay_seconds=10,
            salt=salt,
            sessionmaker=sessionmaker,
            on_active_refresh=on_active_refresh,
        )

    def start(self) -> None:
        if self._task is None:
            self._task = asyncio.create_task(self._loop(), name="jobs-index-scheduler")
            log.info(
                "jobs-index scheduler started (interval=%ds)",
                self._interval_seconds,
            )

    async def stop(self) -> None:
        self._stop.set()
        if self._task is not None:
            try:
                await asyncio.wait_for(self._task, timeout=10)
            except TimeoutError:
                self._task.cancel()
            self._task = None

    async def _loop(self) -> None:
        try:
            await asyncio.wait_for(
                self._stop.wait(), timeout=self._initial_delay_seconds,
            )
            return
        except TimeoutError:
            pass
        await self._tick()
        while not self._stop.is_set():
            try:
                await asyncio.wait_for(
                    self._stop.wait(), timeout=self._interval_seconds,
                )
                break
            except TimeoutError:
                await self._tick()

    async def _tick(self) -> None:
        try:
            async with self._sessionmaker() as session:
                written = await refresh_jobs_index(session, self._salt)
                await session.commit()
            log.info("jobs-index tick: %d jobs indexed", written)
        except Exception:
            log.exception("jobs-index tick failed")
        try:
            active = await refresh_active_jids(self._salt)
            self._on_active_refresh(active, datetime.now(tz=UTC))
            log.debug("jobs-index active refresh: %d active", len(active))
        except Exception:
            log.exception("jobs-index active refresh failed")
