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

_SCHEDULER_JOB_ID = "prm_scheduler_tick"


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
        self._interval_hours: int | None = None

    def start(self, *, run_on_startup: bool = True) -> None:
        interval_hours = self._read_interval_hours()
        self._interval_hours = interval_hours
        self._scheduler.add_job(
            self._run_jobs,
            trigger=IntervalTrigger(hours=interval_hours),
            id=_SCHEDULER_JOB_ID,
            replace_existing=True,
        )
        self._scheduler.start()
        logger.info("Background scheduler started (interval=%s hours)", interval_hours)
        if run_on_startup:
            self._run_jobs()

    def update_interval_hours(self, hours: int) -> None:
        """Reschedule the background tick to a new interval (Option A — admin PATCH)."""
        if self._interval_hours == hours:
            return
        self._interval_hours = hours
        if not self._scheduler.running:
            return
        self._scheduler.reschedule_job(
            _SCHEDULER_JOB_ID,
            trigger=IntervalTrigger(hours=hours),
        )
        logger.info("Scheduler interval rescheduled to %s hours", hours)

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
