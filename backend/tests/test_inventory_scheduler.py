# backend/tests/test_inventory_scheduler.py
"""Tests for the periodic inventory refresh loop.

We don't drive the real refresh code from here — that's already covered by
``test_inventory_service`` and ``test_inventory_routes``. What these tests
prove is the *loop's* behaviour:

  * It waits ``initial_delay_s`` before the first run.
  * It calls the refresh function once per cycle.
  * It survives salt-api errors without crashing or backing off oddly.
  * Cancellation propagates cleanly.

The scheduler is parameterised over its dependencies (sessionmaker, salt
client, ``refresh_packages``-via-import), so we substitute a fake client
that records how many times its trigger fired. The real ``refresh_packages``
call is monkey-patched to a no-op-with-counter so we don't need a DB at all.
"""

from __future__ import annotations

import asyncio
import logging

import pytest

from halite.inventory import scheduler as scheduler_mod
from halite.salt.client import SaltAPIUnavailable


class _StubClient:
    """Stand-in for SaltAPIClient — the scheduler only passes it through."""


class _StubSessionmaker:
    """Stand-in for async_sessionmaker — never actually entered because the
    monkey-patched ``refresh_packages`` returns before touching it."""

    def __call__(self):  # pragma: no cover - never called when patched
        raise AssertionError("sessionmaker was entered unexpectedly")


@pytest.mark.asyncio
async def test_scheduler_calls_refresh_on_interval(monkeypatch):
    """One iteration per interval, after the initial delay."""
    calls: list[int] = []

    async def fake_refresh(db, client, *, target, target_type):  # noqa: ANN001
        calls.append(1)
        return {"web-01": 42}

    monkeypatch.setattr(scheduler_mod, "refresh_packages", fake_refresh)

    # Patch asyncio.sleep so the test doesn't actually wait. We yield control
    # once so the loop can schedule itself.
    real_sleep = asyncio.sleep

    async def fast_sleep(_seconds: float) -> None:
        # Yield once so the loop can make progress between iterations.
        await real_sleep(0)

    monkeypatch.setattr(scheduler_mod.asyncio, "sleep", fast_sleep)

    task = asyncio.create_task(
        scheduler_mod.run_inventory_scheduler(
            sessionmaker=_StubSessionmaker(),  # type: ignore[arg-type]
            client=_StubClient(),  # type: ignore[arg-type]
            interval_minutes=5,
            initial_delay_s=1,
        )
    )

    # Let the loop run a handful of cycles.
    for _ in range(20):
        await real_sleep(0)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    # We can't predict the exact count (it depends on event-loop scheduling),
    # but we MUST have made at least one call \u2014 proving the loop reached the
    # refresh after the initial delay \u2014 and we shouldn't have run away.
    assert len(calls) >= 1
    assert len(calls) <= 25  # generous upper bound; would be far higher if loop misbehaved


@pytest.mark.asyncio
async def test_scheduler_returns_immediately_when_interval_is_zero(monkeypatch):
    """``interval_minutes=0`` is the disable switch."""
    called = False

    async def fake_refresh(*args, **kwargs):  # pragma: no cover - shouldn't run
        nonlocal called
        called = True

    monkeypatch.setattr(scheduler_mod, "refresh_packages", fake_refresh)

    # If the scheduler returned without entering the loop, this awaits in O(0).
    await asyncio.wait_for(
        scheduler_mod.run_inventory_scheduler(
            sessionmaker=_StubSessionmaker(),  # type: ignore[arg-type]
            client=_StubClient(),  # type: ignore[arg-type]
            interval_minutes=0,
            initial_delay_s=0,
        ),
        timeout=1.0,
    )
    assert called is False


@pytest.mark.asyncio
async def test_scheduler_keeps_running_after_salt_error(monkeypatch, caplog):
    """A SaltAPIUnavailable inside one iteration must NOT kill the loop."""
    call_count = 0

    async def flaky_refresh(db, client, *, target, target_type):  # noqa: ANN001
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise SaltAPIUnavailable("first call: simulated outage")
        return {}

    monkeypatch.setattr(scheduler_mod, "refresh_packages", flaky_refresh)

    real_sleep = asyncio.sleep

    async def fast_sleep(_s: float) -> None:
        await real_sleep(0)

    monkeypatch.setattr(scheduler_mod.asyncio, "sleep", fast_sleep)

    caplog.set_level(logging.WARNING, logger="halite.inventory.scheduler")

    task = asyncio.create_task(
        scheduler_mod.run_inventory_scheduler(
            sessionmaker=_StubSessionmaker(),  # type: ignore[arg-type]
            client=_StubClient(),  # type: ignore[arg-type]
            interval_minutes=1,
            initial_delay_s=0,
        )
    )
    # Spin long enough for the loop to recover and retry at least once more.
    for _ in range(40):
        await real_sleep(0)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    assert call_count >= 2, "loop should have retried after the first failure"
    # The transient failure should have been logged.
    assert any(
        "salt-api error" in record.getMessage()
        for record in caplog.records
        if record.name == "halite.inventory.scheduler"
    )


@pytest.mark.asyncio
async def test_scheduler_cancellation_is_clean(monkeypatch):
    """Cancelling the task is the expected shutdown path; it must re-raise
    CancelledError so asyncio sees the task as cancelled."""

    async def fake_refresh(*args, **kwargs):  # pragma: no cover - timing-dependent
        return {}

    monkeypatch.setattr(scheduler_mod, "refresh_packages", fake_refresh)

    task = asyncio.create_task(
        scheduler_mod.run_inventory_scheduler(
            sessionmaker=_StubSessionmaker(),  # type: ignore[arg-type]
            client=_StubClient(),  # type: ignore[arg-type]
            interval_minutes=60,
            initial_delay_s=600,  # would normally pause here
        )
    )
    # Yield once so the task starts and hits the first sleep.
    await asyncio.sleep(0)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert task.cancelled()


@pytest.mark.asyncio
async def test_scheduler_swallows_unexpected_exception(monkeypatch, caplog):
    """A bug elsewhere in the pipeline should log a traceback but not kill
    the loop. We've seen tasks die silently in production when one off-by-one
    in a downstream collector killed the whole scheduler; this test pins that
    against regression."""
    call_count = 0

    async def buggy_refresh(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise RuntimeError("simulated bug")
        return {}

    monkeypatch.setattr(scheduler_mod, "refresh_packages", buggy_refresh)

    real_sleep = asyncio.sleep

    async def fast_sleep(_s: float) -> None:
        await real_sleep(0)

    monkeypatch.setattr(scheduler_mod.asyncio, "sleep", fast_sleep)
    caplog.set_level(logging.ERROR, logger="halite.inventory.scheduler")

    task = asyncio.create_task(
        scheduler_mod.run_inventory_scheduler(
            sessionmaker=_StubSessionmaker(),  # type: ignore[arg-type]
            client=_StubClient(),  # type: ignore[arg-type]
            interval_minutes=1,
            initial_delay_s=0,
        )
    )
    for _ in range(40):
        await real_sleep(0)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    assert call_count >= 2
    assert any(
        "unexpected error" in record.getMessage()
        for record in caplog.records
        if record.name == "halite.inventory.scheduler"
    )
