"""Application configuration loaded from environment variables."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

from prm import __version__
from prm.domain.constants import DEFAULT_MAX_WEEKLY_HOURS, DEFAULT_SCHEDULER_INTERVAL_HOURS


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "PRM API"
    app_version: str = __version__
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    database_url: str = "postgresql://prm:prm@localhost:5432/prm"

    bootstrap_admin_username: str
    bootstrap_admin_password: str
    bootstrap_admin_full_name: str
    bootstrap_admin_email: str

    jwt_secret_key: str
    jwt_expire_minutes: int = 480

    # First-run system config seed only (skipped once a row exists; later changes via admin API)
    bootstrap_llm_provider: str = "GEMINI"
    bootstrap_llm_api_key: str = ""
    bootstrap_scheduler_interval_hours: int = DEFAULT_SCHEDULER_INTERVAL_HOURS
    bootstrap_max_weekly_hours: int = DEFAULT_MAX_WEEKLY_HOURS


@lru_cache
def get_settings() -> Settings:
    return Settings()
