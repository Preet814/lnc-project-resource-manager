"""Console client configuration (environment-driven)."""

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class ConsoleConfig:
    api_base_url: str
    max_health_attempts: int = 30
    health_retry_seconds: float = 2.0

    @classmethod
    def from_env(cls) -> "ConsoleConfig":
        return cls(
            api_base_url=os.getenv("API_BASE_URL", "http://localhost:8000"),
            max_health_attempts=int(os.getenv("CONSOLE_HEALTH_MAX_ATTEMPTS", "30")),
            health_retry_seconds=float(os.getenv("CONSOLE_HEALTH_RETRY_SECONDS", "2")),
        )
