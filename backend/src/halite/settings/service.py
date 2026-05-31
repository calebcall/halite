from __future__ import annotations

import logging
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from halite.settings.crypto import decrypt_password, encrypt_password
from halite.settings.models import AppSettings
from halite.settings.schemas import (
    LoggingSettingsIn,
    LoggingSettingsOut,
    PollerSettingsIn,
    PollerSettingsOut,
    SaltSettingsIn,
    SaltSettingsOut,
    SettingsOut,
    SettingsStatusOut,
)

log = logging.getLogger(__name__)


async def _row(db: AsyncSession) -> AppSettings:
    row = (await db.execute(select(AppSettings))).scalar_one_or_none()
    if row is None:
        # Migration always seeds row 1, but be defensive in case of a
        # bare/test DB.
        row = AppSettings(id=1, updated_at=datetime.now(tz=UTC))
        db.add(row)
        await db.flush()
    return row


async def get_settings(db: AsyncSession) -> SettingsOut:
    row = await _row(db)
    return SettingsOut(
        salt=SaltSettingsOut(
            url=row.salt_api_url,
            username=row.salt_api_username,
            password_set=bool(row.salt_api_password_encrypted),
            verify=row.salt_api_verify,
            eauth=row.salt_api_eauth,  # type: ignore[arg-type]
        ),
        pollers=PollerSettingsOut(
            inventory_refresh_minutes=row.inventory_refresh_minutes,
            inventory_refresh_initial_delay_s=row.inventory_refresh_initial_delay_s,
            fleet_poll_interval_seconds=row.fleet_poll_interval_seconds,
            jobs_poll_interval_seconds=row.jobs_poll_interval_seconds,
            minion_state_keys_interval_seconds=row.minion_state_keys_interval_seconds,
            minion_state_presence_interval_seconds=row.minion_state_presence_interval_seconds,
            minion_state_grains_interval_seconds=row.minion_state_grains_interval_seconds,
            minion_state_initial_delay_seconds=row.minion_state_initial_delay_seconds,
            event_stream_enabled=row.event_stream_enabled,
            event_stream_retention_days=row.event_stream_retention_days,
        ),
        logging=LoggingSettingsOut(log_format=row.log_format),  # type: ignore[arg-type]
        updated_at=row.updated_at,
    )


async def get_settings_status(db: AsyncSession) -> SettingsStatusOut:
    row = await _row(db)
    missing: list[str] = []
    if not row.salt_api_url:
        missing.append("salt.url")
    if not row.salt_api_username:
        missing.append("salt.username")
    if not row.salt_api_password_encrypted:
        missing.append("salt.password")
    return SettingsStatusOut(configured=len(missing) == 0, missing=missing)


async def update_salt(
    db: AsyncSession, patch: SaltSettingsIn, *, cookie_secret: str
) -> AppSettings:
    row = await _row(db)
    if patch.url is not None:
        row.salt_api_url = str(patch.url).rstrip("/")
    if patch.username is not None:
        row.salt_api_username = patch.username
    if patch.password is not None:
        row.salt_api_password_encrypted = encrypt_password(
            patch.password.get_secret_value(), cookie_secret=cookie_secret
        )
    if patch.verify is not None:
        row.salt_api_verify = patch.verify
    if patch.eauth is not None:
        row.salt_api_eauth = patch.eauth
    row.updated_at = datetime.now(tz=UTC)
    return row


async def update_pollers(db: AsyncSession, patch: PollerSettingsIn) -> AppSettings:
    row = await _row(db)
    for field in (
        "inventory_refresh_minutes",
        "inventory_refresh_initial_delay_s",
        "fleet_poll_interval_seconds",
        "jobs_poll_interval_seconds",
        "minion_state_keys_interval_seconds",
        "minion_state_presence_interval_seconds",
        "minion_state_grains_interval_seconds",
        "minion_state_initial_delay_seconds",
        "event_stream_enabled",
        "event_stream_retention_days",
    ):
        v = getattr(patch, field)
        if v is not None:
            setattr(row, field, v)
    row.updated_at = datetime.now(tz=UTC)
    return row


async def update_logging(db: AsyncSession, patch: LoggingSettingsIn) -> AppSettings:
    row = await _row(db)
    if patch.log_format is not None:
        row.log_format = patch.log_format
    row.updated_at = datetime.now(tz=UTC)
    return row


def decrypt_salt_password(row: AppSettings, *, cookie_secret: str) -> str | None:
    """Used by RuntimeConfig when (re)building the salt client."""
    if not row.salt_api_password_encrypted:
        return None
    return decrypt_password(row.salt_api_password_encrypted, cookie_secret=cookie_secret)
