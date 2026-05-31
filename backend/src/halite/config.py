from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=None, env_prefix="", extra="ignore", populate_by_name=True)

    database_url: str = Field(..., description="SQLAlchemy URL")

    cookie_secret: str = Field(..., description=">=32 bytes signing key")
    session_ttl_minutes: int = 480
    cookie_secure: bool = True
    cookie_name: str = "halite_session"

    listen_host: str = "0.0.0.0"
    listen_port: int = 8080
    trusted_proxies: str = ""

    log_level: str = "info"

    audit_audit_reads: bool = False

    # Fleet background scheduler (infra-level tuning; not in AppSettings).
    fleet_highstate_funs: list[str] = ["state.apply", "state.highstate", "state.sls"]
    fleet_lookback_minutes: int = 60

    # Static SPA — path to the built frontend dist. None disables SPA serving.
    static_dir: str | None = Field(default=None, validation_alias="HALITE_STATIC_DIR")

    # ---- Demo mode ----
    demo_mode: bool = Field(default=False, validation_alias="HALITE_DEMO_MODE")
    demo_admin_password: str = "halite-demo-admin"   # DEMO_ADMIN_PASSWORD
    demo_salt_url: str = "http://mock-salt-api:8000"  # DEMO_SALT_URL
    demo_salt_username: str = "halite-demo"           # DEMO_SALT_USERNAME
    demo_salt_password: str = "demo"                  # DEMO_SALT_PASSWORD

    @field_validator("cookie_secret")
    @classmethod
    def _validate_secret(cls, v: str) -> str:
        if len(v) < 32:
            raise ValueError("COOKIE_SECRET must be at least 32 characters")
        return v


def get_settings() -> Settings:
    return Settings()
