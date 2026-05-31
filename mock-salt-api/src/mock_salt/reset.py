from __future__ import annotations

import asyncio

from mock_salt.fleet import build_fleet


class ResetLoop:
    """Periodically re-seeds the fleet to baseline so the shared demo stays clean.
    Mutates the passed-in state holder's `.fleet` attribute in place."""

    def __init__(self, holder, *, minutes: int, seed: int, size: int) -> None:
        self._holder = holder
        self._interval = minutes * 60
        self._seed = seed
        self._size = size
        self._task: asyncio.Task | None = None

    async def _run(self) -> None:
        while True:
            await asyncio.sleep(self._interval)
            self._holder.fleet = build_fleet(seed=self._seed, size=self._size)

    def start(self) -> None:
        if self._interval > 0 and self._task is None:
            self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            self._task = None
