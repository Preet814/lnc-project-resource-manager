"""Application configuration loaded from environment variables."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

from prm import __version__


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


@lru_cache
def get_settings() -> Settings:
    return Settings()
