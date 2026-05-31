import pytest

from mock_salt.events import EventBus
from mock_salt.fleet import build_fleet
from mock_salt.simulator import Simulator


@pytest.mark.asyncio
async def test_tick_emits_a_job_lifecycle():
    fleet = build_fleet(seed=1, size=10)
    bus = EventBus()
    sim = Simulator(fleet, bus, rng_seed=1)
    collected = []
    with bus.subscribe() as q:
        await sim.tick()
        while not q.empty():
            collected.append(await q.get())
    tags = [t for t, _ in collected]
    assert any(t.endswith("/new") for t in tags)
    assert any("/ret/" in t for t in tags)


@pytest.mark.asyncio
async def test_tick_adds_a_job_to_fleet():
    fleet = build_fleet(seed=1, size=10)
    before = len(fleet.jobs)
    sim = Simulator(fleet, EventBus(), rng_seed=1)
    await sim.tick()
    assert len(fleet.jobs) == before + 1
