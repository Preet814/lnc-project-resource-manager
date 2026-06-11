"""APScheduler wiring for background PRM jobs (BRD §4.1)."""

import logging
from collections.abc import Callable

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy.orm import Session, sessionmaker

from prm.domain.constants import DEFAULT_SCHEDULER_INTERVAL_HOURS
from prm.infrastructure.db.repositories import SqlAlchemySystemConfigurationRepository
from prm.scheduler.factory import create_scheduler_service

logger = logging.getLogger(__name__)


class SchedulerRunner:
    """Start and stop APScheduler ticks that run SchedulerService jobs."""

    def __init__(
        self,
        session_factory: sessionmaker[Session],
        *,
        read_interval_hours: Callable[[], int] | None = None,
        run_jobs: Callable[[], None] | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._scheduler = BackgroundScheduler()
        self._read_interval_hours = read_interval_hours or self._load_interval_hours
        self._run_jobs = run_jobs or self._execute_jobs

    def start(self, *, run_on_startup: bool = True) -> None:
        interval_hours = self._read_interval_hours()
        self._scheduler.add_job(
            self._run_jobs,
            trigger=IntervalTrigger(hours=interval_hours),
            id="prm_scheduler_tick",
            replace_existing=True,
        )
        self._scheduler.start()
        logger.info("Background scheduler started (interval=%s hours)", interval_hours)
        if run_on_startup:
            self._run_jobs()

    def shutdown(self) -> None:
        if self._scheduler.running:
            self._scheduler.shutdown(wait=False)
            logger.info("Background scheduler stopped")

    def _load_interval_hours(self) -> int:
        session = self._session_factory()
        try:
            config = SqlAlchemySystemConfigurationRepository(session).find_singleton()
            if config is None:
                return DEFAULT_SCHEDULER_INTERVAL_HOURS
            return config.scheduler_interval_hours
        finally:
            session.close()

    def _execute_jobs(self) -> None:
        session = self._session_factory()
        try:
            service = create_scheduler_service(session)
            result = service.run_all_jobs()
            session.commit()
            logger.info(
                "Scheduler tick complete (engineers=%s projects=%s missed=%s)",
                result.engineers_synced,
                result.projects_evaluated,
                result.missed_weeks_created,
            )
        except Exception:
            session.rollback()
            logger.exception("Background scheduler job failed")
        finally:
            session.close()
