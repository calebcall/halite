from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from halite.minions.ingest import refresh_grains, refresh_keys, refresh_presence
from halite.salt.client import SaltAPIClient

if TYPE_CHECKING:
    from halite.settings.models import AppSettings

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class _Intervals:
    keys: int
    presence: int
    grains: int
    initial_delay: int


class MinionStateScheduler:
    """Three independent loops — keys / presence / grains. Each is opt-in
    via its own interval. Disable a loop by leaving its interval at 0.

    All three loops call master-side runner/wheel functions. None of
    them touch minions directly."""

    def __init__(
        self,
        intervals: _Intervals,
        salt: SaltAPIClient,
        sessionmaker: async_sessionmaker[AsyncSession],
    ) -> None:
        self._intervals = intervals
        self._salt = salt
        self._sessionmaker = sessionmaker
        self._stop = asyncio.Event()
        self._tasks: list[asyncio.Task[None]] = []

    @classmethod
    def from_row(
        cls,
        row: AppSettings,
        salt: SaltAPIClient,
        sessionmaker: async_sessionmaker[AsyncSession],
    ) -> MinionStateScheduler:
        return cls(
            intervals=_Intervals(
                keys=row.minion_state_keys_interval_seconds,
                presence=row.minion_state_presence_interval_seconds,
                grains=row.minion_state_grains_interval_seconds,
                initial_delay=row.minion_state_initial_delay_seconds,
            ),
            salt=salt,
            sessionmaker=sessionmaker,
        )

    def start(self) -> None:
        iv = self._intervals
        started: list[str] = []
        if iv.keys > 0:
            self._tasks.append(asyncio.create_task(
                self._loop("keys", iv.keys, self._tick_keys),
                name="minion-keys-scheduler",
            ))
            started.append(f"keys={iv.keys}s")
        if iv.presence > 0:
            self._tasks.append(asyncio.create_task(
                self._loop("presence", iv.presence, self._tick_presence),
                name="minion-presence-scheduler",
            ))
            started.append(f"presence={iv.presence}s")
        if iv.grains > 0:
            self._tasks.append(asyncio.create_task(
                self._loop("grains", iv.grains, self._tick_grains),
                name="minion-grains-scheduler",
            ))
            started.append(f"grains={iv.grains}s")
        if started:
            log.info("minion-state scheduler started: %s", " ".join(started))

    async def stop(self) -> None:
        self._stop.set()
        for t in self._tasks:
            try:
                await asyncio.wait_for(t, timeout=10)
            except TimeoutError:
                t.cancel()
        self._tasks.clear()

    async def reconfigure(self, intervals: _Intervals) -> None:
        await self.stop()
        self._intervals = intervals
        self._stop = asyncio.Event()
        self.start()

    async def _loop(
        self, name: str, interval: int, tick: Callable[[], Awaitable[None]],
    ) -> None:
        # Interruptible grace period at startup.
        try:
            await asyncio.wait_for(
                self._stop.wait(),
                timeout=self._intervals.initial_delay,
            )
            return
        except TimeoutError:
            pass
        await tick()
        while not self._stop.is_set():
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=interval)
                break
            except TimeoutError:
                await tick()

    async def _tick_keys(self) -> None:
        try:
            async with self._sessionmaker() as session:
                touched = await refresh_keys(session, self._salt)
                await session.commit()
            log.info("minion keys: %d rows touched", touched)
        except Exception:
            log.exception("minion keys refresh failed")

    async def _tick_presence(self) -> None:
        try:
            async with self._sessionmaker() as session:
                touched = await refresh_presence(session, self._salt)
                await session.commit()
            log.debug("minion presence: %d rows updated", touched)
        except Exception:
            log.exception("minion presence refresh failed")

    async def _tick_grains(self) -> None:
        try:
            async with self._sessionmaker() as session:
                touched = await refresh_grains(session, self._salt)
                await session.commit()
            log.info("minion grains: %d rows touched", touched)
        except Exception:
            log.exception("minion grains refresh failed")
