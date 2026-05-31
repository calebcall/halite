from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Settings:
    username: str = field(default_factory=lambda: os.getenv("MOCK_SALT_USERNAME", "halite-demo"))
    password: str = field(default_factory=lambda: os.getenv("MOCK_SALT_PASSWORD", "demo"))
    eauth: str = field(default_factory=lambda: os.getenv("MOCK_SALT_EAUTH", "pam"))
    reset_minutes: int = field(default_factory=lambda: int(os.getenv("MOCK_RESET_MINUTES", "30")))
    fleet_size: int = field(default_factory=lambda: int(os.getenv("MOCK_FLEET_SIZE", "40")))
    fleet_seed: int = field(default_factory=lambda: int(os.getenv("MOCK_FLEET_SEED", "1337")))
    sim_interval_seconds: float = field(default_factory=lambda: float(os.getenv("MOCK_SIM_INTERVAL_S", "6")))
