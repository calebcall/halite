"""RuntimeConfig — owns the live salt client and all background schedulers.

Pattern:
  settings live in DB → on PUT, the route writes the DB, then calls
  ``runtime.reload(db)`` → RuntimeConfig tears down current wirings and
  rebuilds with the new values.

At boot, if the DB row has no salt credentials, the client is None and no
schedulers start. Everything degrades gracefully to empty responses.
"""

from __future__ import annotations

import logging
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from halite.activity.consumer import EventStreamConsumer
from halite.activity.hub import EventHub
from halite.config import Settings
from halite.fleet.scheduler import FleetIngestScheduler
from halite.inventory.scheduler import InventoryScheduler
from halite.jobs.scheduler import JobsIndexScheduler
from halite.minions.scheduler import MinionStateScheduler
from halite.salt.client import SaltAPIClient
from halite.settings.models import AppSettings
from halite.settings.service import decrypt_salt_password

log = logging.getLogger(__name__)


class RuntimeConfig:
    """Owns the live salt client + the schedulers.

    On ``reload(db)``, tears down current wirings and rebuilds from the
    current AppSettings row. On ``shutdown()``, stops everything cleanly."""

    def __init__(
        self,
        infra: Settings,
        sessionmaker: async_sessionmaker[AsyncSession],
    ) -> None:
        self._infra = infra
        self._sessionmaker = sessionmaker
        self.salt: SaltAPIClient | None = None
        self.minion_scheduler: MinionStateScheduler | None = None
        self.fleet_scheduler: FleetIngestScheduler | None = None
        self.inventory_scheduler: InventoryScheduler | None = None
        self.jobs_scheduler: JobsIndexScheduler | None = None
        self.active_jids: set[str] | None = None
        self.active_jids_refreshed_at: datetime | None = None
        self.event_hub: EventHub | None = None
        self.event_consumer: EventStreamConsumer | None = None

    async def boot(self, db: AsyncSession) -> None:
        """Wire up salt client and schedulers from the current DB row."""
        row = await self._load_row(db)
        await self._wire(row)

    async def reload(self, db: AsyncSession) -> None:
        """Atomically tear down and rebuild wiring from the current DB row."""
        row = await self._load_row(db)
        log.info("RuntimeConfig.reload: rewiring salt client + schedulers")
        await self._teardown()
        await self._wire(row)

    async def shutdown(self) -> None:
        """Stop all schedulers and close the salt client."""
        await self._teardown()

    def _on_active_jids_refresh(self, jids: set[str], at: datetime) -> None:
        self.active_jids = jids
        self.active_jids_refreshed_at = at

    async def _load_row(self, db: AsyncSession) -> AppSettings:
        return (await db.execute(select(AppSettings))).scalar_one()

    async def _teardown(self) -> None:
        if self.minion_scheduler is not None:
            try:
                await self.minion_scheduler.stop()
            except Exception:
                log.exception("minion scheduler teardown failed")
            self.minion_scheduler = None
        if self.fleet_scheduler is not None:
            try:
                await self.fleet_scheduler.stop()
            except Exception:
                log.exception("fleet scheduler teardown failed")
            self.fleet_scheduler = None
        if self.inventory_scheduler is not None:
            try:
                await self.inventory_scheduler.stop()
            except Exception:
                log.exception("inventory scheduler teardown failed")
            self.inventory_scheduler = None
        if self.jobs_scheduler is not None:
            try:
                await self.jobs_scheduler.stop()
            except Exception:
                log.exception("jobs scheduler teardown failed")
            self.jobs_scheduler = None
        self.active_jids = None
        self.active_jids_refreshed_at = None
        if self.event_consumer is not None:
            try:
                await self.event_consumer.stop()
            except Exception:
                log.exception("event consumer teardown failed")
            self.event_consumer = None
        self.event_hub = None
        if self.salt is not None:
            try:
                await self.salt.aclose()
            except Exception:
                log.exception("salt client teardown failed")
            self.salt = None

    async def _wire(self, row: AppSettings) -> None:
        password = decrypt_salt_password(row, cookie_secret=self._infra.cookie_secret)
        if not (row.salt_api_url and row.salt_api_username and password):
            log.info("RuntimeConfig: salt is unconfigured — schedulers will not start")
            return

        client = SaltAPIClient(
            base_url=row.salt_api_url,
            username=row.salt_api_username,
            password=password,
            eauth=row.salt_api_eauth,
            verify=row.salt_api_verify,
        )
        try:
            await client.login()
        except Exception:
            log.exception("salt-api login failed during boot/reload — client unavailable")
            await client.aclose()
            return
        self.salt = client

        if (
            row.minion_state_keys_interval_seconds > 0
            or row.minion_state_presence_interval_seconds > 0
            or row.minion_state_grains_interval_seconds > 0
        ):
            self.minion_scheduler = MinionStateScheduler.from_row(
                row=row, salt=self.salt, sessionmaker=self._sessionmaker
            )
            self.minion_scheduler.start()

        if row.fleet_poll_interval_seconds > 0:
            self.fleet_scheduler = FleetIngestScheduler.from_row(
                row=row,
                salt=self.salt,
                sessionmaker=self._sessionmaker,
                highstate_funs=self._infra.fleet_highstate_funs,
                lookback_minutes=self._infra.fleet_lookback_minutes,
            )
            self.fleet_scheduler.start()

        if row.inventory_refresh_minutes > 0:
            self.inventory_scheduler = InventoryScheduler.from_row(
                row=row, salt=self.salt, sessionmaker=self._sessionmaker
            )
            self.inventory_scheduler.start()

        if row.jobs_poll_interval_seconds > 0:
            self.jobs_scheduler = JobsIndexScheduler.from_row(
                row,
                salt=self.salt,
                sessionmaker=self._sessionmaker,
                on_active_refresh=self._on_active_jids_refresh,
            )
            self.jobs_scheduler.start()

        if row.event_stream_enabled:
            self.event_hub = EventHub()
            self.event_consumer = EventStreamConsumer.from_row(
                row, salt=self.salt, sessionmaker=self._sessionmaker, hub=self.event_hub
            )
            self.event_consumer.start()
