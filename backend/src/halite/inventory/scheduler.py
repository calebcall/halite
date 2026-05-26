# backend/src/halite/inventory/scheduler.py
"""Periodic, in-process inventory collection.

This is a deliberately small piece of code. A single ``asyncio.Task`` runs
in the FastAPI event loop, calling ``refresh_packages(target='*')`` every
``Settings.inventory_refresh_minutes`` minutes. No external scheduler,
no cron, no celery — for a homelab-to-mid-fleet salt console that's
overkill.

Design rules
------------

* **Opt-in.** ``inventory_refresh_minutes=0`` (the default) disables the
  scheduler entirely. Existing deployments that upgrade keep their old
  behaviour until they choose to turn it on.
* **Don't pile up.** One iteration completes (or fails) before the next is
  considered. We use ``asyncio.sleep`` between runs, not a wall-clock alarm,
  so a slow refresh doesn't queue more refreshes behind it.
* **Quiet on transient failure.** Salt-api hiccups (5xx, network blip) are
  logged at WARNING and the loop sleeps the normal interval — no exponential
  backoff, no alerting, no death-spiral. A persistent outage shows up as a
  steady stream of warnings; nothing crashes.
* **Cancellable.** Lifespan shutdown cancels the task and awaits it; the
  task swallows ``CancelledError`` cleanly and re-raises so asyncio sees it.
* **No DB session is held across the sleep.** Each iteration opens its own
  ``AsyncSession``, runs one refresh, closes the session, then sleeps.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import TYPE_CHECKING

from halite.inventory.service import refresh_packages
from halite.salt.client import SaltAPIError, SaltAPIUnavailable

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    from halite.salt.client import SaltAPIClient

logger = logging.getLogger(__name__)


async def run_inventory_scheduler(
    *,
    sessionmaker: async_sessionmaker[AsyncSession],
    client: SaltAPIClient,
    interval_minutes: int,
    initial_delay_s: int = 30,
) -> None:
    """Run the periodic inventory refresh loop forever.

    Returns only when cancelled. Callers should fire-and-forget this with
    ``asyncio.create_task`` and cancel + await the task during shutdown.

    The interval is enforced as "wait N minutes *after* the previous run
    finishes" rather than "fire every N minutes regardless" — a refresh
    that takes 2 minutes on a 5-minute interval still waits 5 more minutes
    after completion, not 3. That's the simpler invariant and avoids the
    overrun-pileup problem.
    """
    if interval_minutes <= 0:
        # Defensive: caller should have checked, but never start a no-op loop.
        return

    interval_s = interval_minutes * 60
    logger.info(
        "inventory scheduler starting: every %dm (first run in %ds)",
        interval_minutes,
        initial_delay_s,
    )

    try:
        # Initial delay so we don't pile onto a fresh-startup salt-master.
        await asyncio.sleep(initial_delay_s)

        while True:
            started = time.monotonic()
            try:
                await _refresh_once(sessionmaker, client)
            except asyncio.CancelledError:
                raise  # propagate
            except (SaltAPIUnavailable, SaltAPIError) as exc:
                # Expected transient errors — log and keep looping.
                logger.warning("inventory scheduler: salt-api error: %r", exc)
            except Exception:
                # Anything else is a real bug somewhere in the pipeline.
                # Log with traceback, then keep looping — we'd rather miss a
                # cycle than take the whole app down.
                logger.exception("inventory scheduler: unexpected error")
            elapsed = time.monotonic() - started
            # Cap negative sleep at 0 (defensive — shouldn't happen).
            await asyncio.sleep(max(0.0, interval_s - elapsed))
    except asyncio.CancelledError:
        logger.info("inventory scheduler stopping")
        raise


async def _refresh_once(
    sessionmaker: async_sessionmaker[AsyncSession],
    client: SaltAPIClient,
) -> None:
    """One refresh iteration. Owns its own DB session."""
    async with sessionmaker() as db:
        # ``refresh_packages`` commits on its own.
        counts = await refresh_packages(db, client, target="*", target_type="glob")
    logger.info(
        "inventory scheduler: refreshed %d minion(s) (total packages=%d)",
        len(counts),
        sum(counts.values()),
    )
