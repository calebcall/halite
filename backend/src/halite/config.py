from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=None, env_prefix="", extra="ignore")

    database_url: str = Field(..., description="SQLAlchemy URL")

    cookie_secret: str = Field(..., description=">=32 bytes signing key")
    session_ttl_minutes: int = 480
    cookie_secure: bool = True
    cookie_name: str = "halite_session"

    salt_api_url: str | None = None
    salt_api_verify: str = "true"
    salt_api_eauth: str = "pam"
    salt_api_username: str | None = None
    salt_api_password: str | None = None

    bootstrap_admin_username: str | None = None
    bootstrap_admin_password: str | None = None

    listen_host: str = "0.0.0.0"
    listen_port: int = 8080
    trusted_proxies: str = ""

    log_level: str = "info"
    log_format: str = "json"

    audit_audit_reads: bool = False

    # Fleet background scheduler.
    fleet_highstate_funs: list[str] = ["state.apply", "state.highstate", "state.sls"]
    fleet_lookback_minutes: int = 60
    # 0 disables the timer; data can still be ingested on demand.
    fleet_poll_interval_seconds: int = 300

    # Inventory background scheduler.
    # 0 disables the timer; manual refreshes via the UI still work either way.
    inventory_refresh_minutes: int = 0
    # Seconds between process start and the first scheduled refresh.
    inventory_refresh_initial_delay_s: int = 30

    # Static SPA — path to the built frontend dist. None disables SPA serving.
    static_dir: str | None = Field(default=None, validation_alias="HALITE_STATIC_DIR")

    @field_validator("cookie_secret")
    @classmethod
    def _validate_secret(cls, v: str) -> str:
        if len(v) < 32:
            raise ValueError("COOKIE_SECRET must be at least 32 characters")
        return v


def get_settings() -> Settings:
    return Settings()
