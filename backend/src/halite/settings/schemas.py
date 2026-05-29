from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, SecretStr, model_validator

EauthBackend = Literal["pam", "sharedsecret", "ldap", "file", "auto"]
LogFormat = Literal["json", "text"]


class SaltSettingsOut(BaseModel):
    """Salt API connection settings. Password is never returned — only
    a boolean ``password_set`` so the UI can render \"(set)\" without
    exposing the value."""

    url: str | None
    username: str | None
    password_set: bool
    verify: bool
    eauth: EauthBackend


class PollerSettingsOut(BaseModel):
    inventory_refresh_minutes: int
    inventory_refresh_initial_delay_s: int
    fleet_poll_interval_seconds: int
    jobs_poll_interval_seconds: int
    minion_state_keys_interval_seconds: int
    minion_state_presence_interval_seconds: int
    minion_state_grains_interval_seconds: int
    minion_state_initial_delay_seconds: int
    event_stream_enabled: bool
    event_stream_retention_days: int


class LoggingSettingsOut(BaseModel):
    log_format: LogFormat


class SettingsOut(BaseModel):
    salt: SaltSettingsOut
    pollers: PollerSettingsOut
    logging: LoggingSettingsOut
    updated_at: datetime


class SettingsStatusOut(BaseModel):
    """Used by the setup-wizard guard."""

    configured: bool
    missing: list[str]


class SaltSettingsIn(BaseModel):
    """PUT body for the salt section. All fields optional — only the
    ones present are applied. At least one must be present."""

    model_config = ConfigDict(extra="forbid")

    url: HttpUrl | None = None
    username: str | None = Field(default=None, max_length=255)
    password: SecretStr | None = None
    verify: bool | None = None
    eauth: EauthBackend | None = None

    @model_validator(mode="after")
    def _at_least_one(self) -> SaltSettingsIn:
        if all(
            v is None
            for v in (self.url, self.username, self.password, self.verify, self.eauth)
        ):
            raise ValueError("at least one salt field must be provided")
        return self


class PollerSettingsIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    inventory_refresh_minutes: int | None = Field(default=None, ge=0, le=1440)
    inventory_refresh_initial_delay_s: int | None = Field(default=None, ge=0, le=3600)
    fleet_poll_interval_seconds: int | None = Field(default=None, ge=0, le=86400)
    jobs_poll_interval_seconds: int | None = Field(default=None, ge=0, le=86400)
    minion_state_keys_interval_seconds: int | None = Field(default=None, ge=0, le=86400)
    minion_state_presence_interval_seconds: int | None = Field(default=None, ge=0, le=86400)
    minion_state_grains_interval_seconds: int | None = Field(default=None, ge=0, le=86400)
    minion_state_initial_delay_seconds: int | None = Field(default=None, ge=0, le=3600)
    event_stream_enabled: bool | None = Field(default=None)
    event_stream_retention_days: int | None = Field(default=None, ge=1, le=365)


class LoggingSettingsIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    log_format: LogFormat | None = None


class TestSaltConnectionIn(BaseModel):
    """POST body for the test-connection endpoint. All fields required."""

    model_config = ConfigDict(extra="forbid")

    url: HttpUrl
    username: str = Field(min_length=1, max_length=255)
    password: SecretStr
    verify: bool
    eauth: EauthBackend


class TestSaltConnectionOut(BaseModel):
    ok: bool
    detail: str
    minion_count: int | None = None
