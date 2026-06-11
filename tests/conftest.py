"""Shared pytest configuration."""

import os

import pytest

from prm.api.settings import get_settings
from tests.unit.credentials import TEST_EMAIL, TEST_FULL_NAME, TEST_PASSWORD, TEST_USERNAME


def _apply_unit_test_env() -> None:
    """Isolate unit tests from Docker/.env and disable background scheduler."""
    os.environ["SCHEDULER_ENABLED"] = "false"
    os.environ["SCHEDULER_RUN_ON_STARTUP"] = "false"
    os.environ.setdefault("JWT_SECRET_KEY", "unit-test-jwt-secret-not-for-production-use")
    os.environ.setdefault("BOOTSTRAP_ADMIN_USERNAME", TEST_USERNAME)
    os.environ.setdefault("BOOTSTRAP_ADMIN_PASSWORD", TEST_PASSWORD)
    os.environ.setdefault("BOOTSTRAP_ADMIN_FULL_NAME", TEST_FULL_NAME)
    os.environ.setdefault("BOOTSTRAP_ADMIN_EMAIL", TEST_EMAIL)
    os.environ.setdefault("BOOTSTRAP_LLM_PROVIDER", "GEMINI")
    os.environ.setdefault("BOOTSTRAP_LLM_API_KEY", "")
    os.environ.setdefault("GEMINI_MODEL", "gemini-1.5-flash")
    os.environ.setdefault("GROQ_MODEL", "llama-3.3-70b-versatile")


def _clear_settings_caches() -> None:
    get_settings.cache_clear()
    from prm.infrastructure.db.session import get_engine

    get_engine.cache_clear()


def pytest_configure(config: pytest.Config) -> None:
    """Run before collection so route fixtures never start APScheduler against Postgres."""
    _apply_unit_test_env()
    _clear_settings_caches()


@pytest.fixture(scope="session", autouse=True)
def _disable_scheduler_for_unit_tests() -> None:
    """Re-apply env and clear caches for the test session."""
    _apply_unit_test_env()
    _clear_settings_caches()
