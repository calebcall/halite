"""Periodic, in-process fleet highstate ingestion.

A single ``asyncio.Task`` runs in the FastAPI event loop, calling
``ingest_recent_highstates`` every ``Settings.fleet_poll_interval_seconds``
seconds. The first tick fires immediately on startup so the dashboard has data
on first load without waiting a full interval.

Design rules
------------

* **Opt-in.** ``fleet_poll_interval_seconds=0`` (or unset) disables the
  scheduler. Manual API calls can still trigger ingestion.
* **Tick-then-sleep.** The loop ticks once immediately, then waits for the
  configured interval before each subsequent tick. No pile-up if a tick is slow.
* **Errors are swallowed.** Salt-api hiccups are logged but never crash the
  loop. A persistent outage shows up as a steady stream of log warnings.
* **Clean shutdown.** The task uses ``asyncio.Event`` to wake early on stop;
  ``stop()`` waits up to 10 s then cancels.
* **No session held across sleep.** Each tick opens its own ``AsyncSession``
  and closes it before the next sleep.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from halite.fleet.ingest import ingest_recent_highstates

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    from halite.config import Settings
    from halite.salt.client import SaltAPIClient

log = logging.getLogger(__name__)


class FleetIngestScheduler:
    """Background task that calls ingest_recent_highstates on a fixed
    cadence. Use start()/stop() from app lifespan hooks."""

    def __init__(
        self,
        settings: Settings,
        salt: SaltAPIClient,
        sessionmaker: async_sessionmaker[AsyncSession],
    ) -> None:
        self._settings = settings
        self._salt = salt
        self._sessionmaker = sessionmaker
        self._stop = asyncio.Event()
        self._task: asyncio.Task[None] | None = None
        self._connected_minions: set[str] | None = None
        self._connected_refreshed_at: datetime | None = None

    @property
    def connected_minions(self) -> set[str] | None:
        return self._connected_minions

    @property
    def connected_refreshed_at(self) -> datetime | None:
        return self._connected_refreshed_at

    async def _loop(self) -> None:
        log.info(
            "fleet scheduler started (interval=%ss, funs=%s)",
            self._settings.fleet_poll_interval_seconds,
            self._settings.fleet_highstate_funs,
        )
        # Give the inventory scheduler's startup bulk write a head start so we
        # don't deadlock on the SQLite write lock during cold boot.
        # Uses wait_for so a stop() during the grace period exits cleanly.
        try:
            await asyncio.wait_for(self._stop.wait(), timeout=5)
            return  # stop requested before we even ticked
        except TimeoutError:
            pass
        # Tick once immediately so the dashboard has data on first load.
        await self._tick()
        while not self._stop.is_set():
            try:
                await asyncio.wait_for(
                    self._stop.wait(),
                    timeout=self._settings.fleet_poll_interval_seconds,
                )
                break
            except TimeoutError:
                await self._tick()

    async def _refresh_connectivity(self) -> None:
        try:
            conn_map = await self._salt.list_connected_minions()
            self._connected_minions = set(conn_map.keys())
            self._connected_refreshed_at = datetime.now(tz=UTC)
            log.info("fleet connectivity refreshed: %d minions online", len(self._connected_minions))
        except Exception:
            log.exception("fleet connectivity refresh failed; keeping last-known set")

    async def _tick(self) -> None:
        try:
            async with self._sessionmaker() as session:
                count = await ingest_recent_highstates(
                    session,
                    self._salt,
                    funs=self._settings.fleet_highstate_funs,
                    lookback_minutes=self._settings.fleet_lookback_minutes,
                )
                await session.commit()
            if count:
                log.info("fleet scheduler tick: ingested %d runs", count)
            else:
                log.debug("fleet scheduler tick: 0 new runs")
        except Exception:
            log.exception("fleet scheduler tick failed")
        await self._refresh_connectivity()

    def start(self) -> None:
        if self._task is None:
            self._task = asyncio.create_task(self._loop(), name="fleet-scheduler")

    async def stop(self) -> None:
        self._stop.set()
        if self._task is not None:
            try:
                await asyncio.wait_for(self._task, timeout=10)
            except TimeoutError:
                self._task.cancel()
            self._task = None
