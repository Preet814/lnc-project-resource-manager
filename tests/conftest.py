"""Shared pytest configuration."""

import os

import pytest

from prm.api.settings import get_settings


@pytest.fixture(scope="session", autouse=True)
def _disable_scheduler_for_unit_tests() -> None:
    """TestClient + app lifespan must not start APScheduler for every route fixture."""
    os.environ["SCHEDULER_ENABLED"] = "false"
    get_settings.cache_clear()
