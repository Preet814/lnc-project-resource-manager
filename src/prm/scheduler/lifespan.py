"""FastAPI lifespan hooks for the background scheduler."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from prm.api.settings import get_settings
from prm.infrastructure.db.session import get_session_factory
from prm.scheduler.runner import SchedulerRunner


@asynccontextmanager
async def scheduler_lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Start APScheduler with the API process when enabled in settings."""
    settings = get_settings()
    runner: SchedulerRunner | None = None
    if settings.scheduler_enabled:
        runner = SchedulerRunner(get_session_factory())
        runner.start(run_on_startup=settings.scheduler_run_on_startup)
    try:
        yield
    finally:
        if runner is not None:
            runner.shutdown()
