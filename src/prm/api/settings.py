"""Application configuration loaded from environment variables."""

from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from prm import __version__
from prm.domain.constants import (
    DEFAULT_GEMINI_BASE_URL,
    DEFAULT_GEMINI_MODEL,
    DEFAULT_GROQ_BASE_URL,
    DEFAULT_GROQ_MODEL,
    DEFAULT_MAX_WEEKLY_HOURS,
    DEFAULT_SCHEDULER_INTERVAL_HOURS,
)
from prm.domain.enums import LLMProvider
from prm.infrastructure.llm.validation import validate_llm_base_url, validate_llm_model


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
    scheduler_enabled: bool = True
    scheduler_run_on_startup: bool = True

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

    gemini_base_url: str = DEFAULT_GEMINI_BASE_URL
    gemini_model: str = DEFAULT_GEMINI_MODEL
    groq_base_url: str = DEFAULT_GROQ_BASE_URL
    groq_model: str = DEFAULT_GROQ_MODEL

    @field_validator("gemini_base_url")
    @classmethod
    def validate_gemini_base_url(cls, value: str) -> str:
        return validate_llm_base_url(LLMProvider.GEMINI, value)

    @field_validator("gemini_model")
    @classmethod
    def validate_gemini_model(cls, value: str) -> str:
        return validate_llm_model(value)

    @field_validator("groq_base_url")
    @classmethod
    def validate_groq_base_url(cls, value: str) -> str:
        return validate_llm_base_url(LLMProvider.GROQ, value)

    @field_validator("groq_model")
    @classmethod
    def validate_groq_model(cls, value: str) -> str:
        return validate_llm_model(value)


@lru_cache
def get_settings() -> Settings:
    return Settings()
