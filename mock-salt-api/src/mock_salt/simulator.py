from __future__ import annotations

import asyncio
import random

from mock_salt.dispatch import _local_async
from mock_salt.events import EventBus
from mock_salt.fleet import Fleet

_SIM_FUNS = ["test.ping", "state.apply", "cmd.run", "service.status"]


class Simulator:
    """Periodically dispatches a synthetic job (and occasionally a key-pending
    event) so the live feed moves without any visitor input."""

    def __init__(self, fleet: Fleet, bus: EventBus, *, interval_s: float = 6.0,
                 rng_seed: int | None = None) -> None:
        self._fleet = fleet
        self._bus = bus
        self._interval = interval_s
        self._rng = random.Random(rng_seed)
        self._task: asyncio.Task | None = None

    async def tick(self) -> None:
        fun = self._rng.choice(_SIM_FUNS)
        present = self._fleet.present_ids()
        if not present:
            return
        tgt = self._rng.choice(present)
        await _local_async(self._fleet, self._bus,
                           {"client": "local_async", "fun": fun, "tgt": tgt,
                            "tgt_type": "glob", "arg": []})
        if self._rng.random() < 0.1:
            mid = f"new-minion-{self._rng.randint(100, 999)}.demo.halite"
            await self._bus.publish("salt/key", {"id": mid, "act": "pend"})

    async def _run(self) -> None:
        while True:
            await asyncio.sleep(self._interval)
            try:
                await self.tick()
            except Exception:  # never let the sim loop die
                pass

    def start(self) -> None:
        if self._task is None:
            self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            self._task = None
