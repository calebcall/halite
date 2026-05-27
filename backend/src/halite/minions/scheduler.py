from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from halite.config import Settings
from halite.minions.ingest import refresh_grains, refresh_keys, refresh_presence
from halite.salt.client import SaltAPIClient

log = logging.getLogger(__name__)


class MinionStateScheduler:
    """Three independent loops — keys / presence / grains. Each is opt-in
    via its own ``Settings.minion_state_*_interval_seconds``. Disable a
    loop by leaving its interval at 0 (the default).

    All three loops call master-side runner/wheel functions. None of
    them touch minions directly."""

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
        self._tasks: list[asyncio.Task[None]] = []

    def start(self) -> None:
        s = self._settings
        started: list[str] = []
        if s.minion_state_keys_interval_seconds > 0:
            self._tasks.append(asyncio.create_task(
                self._loop("keys", s.minion_state_keys_interval_seconds, self._tick_keys),
                name="minion-keys-scheduler",
            ))
            started.append(f"keys={s.minion_state_keys_interval_seconds}s")
        if s.minion_state_presence_interval_seconds > 0:
            self._tasks.append(asyncio.create_task(
                self._loop("presence", s.minion_state_presence_interval_seconds, self._tick_presence),
                name="minion-presence-scheduler",
            ))
            started.append(f"presence={s.minion_state_presence_interval_seconds}s")
        if s.minion_state_grains_interval_seconds > 0:
            self._tasks.append(asyncio.create_task(
                self._loop("grains", s.minion_state_grains_interval_seconds, self._tick_grains),
                name="minion-grains-scheduler",
            ))
            started.append(f"grains={s.minion_state_grains_interval_seconds}s")
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

    async def _loop(
        self, name: str, interval: int, tick: Callable[[], Awaitable[None]],
    ) -> None:
        # Interruptible grace period at startup.
        try:
            await asyncio.wait_for(
                self._stop.wait(),
                timeout=self._settings.minion_state_initial_delay_seconds,
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
