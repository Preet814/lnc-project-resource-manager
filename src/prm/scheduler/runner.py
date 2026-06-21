"""APScheduler wiring for background PRM jobs (BRD §4.1)."""

import logging
from collections.abc import Callable
from datetime import date

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy.orm import Session, sessionmaker

from prm.api.settings import Settings, get_settings
from prm.domain.constants import DEFAULT_SCHEDULER_INTERVAL_HOURS
from prm.infrastructure.db.repositories import SqlAlchemySystemConfigurationRepository
from prm.scheduler.factory import (
    create_scheduler_service,
    create_timesheet_notification_service,
)

logger = logging.getLogger(__name__)

_SCHEDULER_JOB_ID = "prm_scheduler_tick"
_TIMESHEET_REMINDER_JOB_ID = "timesheet_reminder"
_TIMESHEET_FREEZE_JOB_ID = "timesheet_freeze"
_TIMESHEET_WEDNESDAY_JOB_ID = "timesheet_wednesday"


class SchedulerRunner:
    """Start and stop APScheduler ticks that run SchedulerService jobs."""

    def __init__(
        self,
        session_factory: sessionmaker[Session],
        *,
        settings: Settings | None = None,
        read_interval_hours: Callable[[], int] | None = None,
        run_jobs: Callable[[], None] | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._settings = settings or get_settings()
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
        if self._settings.timesheet_notifications_enabled:
            timezone = self._settings.app_timezone
            self._scheduler.add_job(
                self._execute_timesheet_reminder,
                trigger=CronTrigger.from_crontab(
                    self._settings.timesheet_reminder_cron,
                    timezone=timezone,
                ),
                id=_TIMESHEET_REMINDER_JOB_ID,
                replace_existing=True,
            )
            self._scheduler.add_job(
                self._execute_timesheet_freeze,
                trigger=CronTrigger.from_crontab(
                    self._settings.timesheet_freeze_cron,
                    timezone=timezone,
                ),
                id=_TIMESHEET_FREEZE_JOB_ID,
                replace_existing=True,
            )
            self._scheduler.add_job(
                self._execute_timesheet_wednesday,
                trigger=CronTrigger.from_crontab(
                    self._settings.timesheet_wednesday_cron,
                    timezone=timezone,
                ),
                id=_TIMESHEET_WEDNESDAY_JOB_ID,
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

    def _execute_timesheet_reminder(self) -> None:
        self._run_timesheet_notification(
            "timesheet reminder",
            lambda service, as_of: service.send_engineer_reminders(as_of),
        )

    def _execute_timesheet_freeze(self) -> None:
        logger.info(
            "Timesheet freeze window active for last completed week (%s)",
            self._settings.app_timezone,
        )

    def _execute_timesheet_wednesday(self) -> None:
        session = self._session_factory()
        try:
            service = create_timesheet_notification_service(session, self._settings)
            as_of = date.today()
            digests = service.send_manager_digests(as_of)
            missed = service.flag_missed_for_last_completed_week(as_of)
            session.commit()
            logger.info(
                "Timesheet Wednesday jobs complete (digests=%s missed=%s)",
                digests,
                missed,
            )
        except Exception:
            session.rollback()
            logger.exception("Timesheet Wednesday notification job failed")
        finally:
            session.close()

    def _run_timesheet_notification(
        self,
        label: str,
        action: Callable,
    ) -> None:
        session = self._session_factory()
        try:
            service = create_timesheet_notification_service(session, self._settings)
            count = action(service, date.today())
            session.commit()
            logger.info("Timesheet %s job complete (sent=%s)", label, count)
        except Exception:
            session.rollback()
            logger.exception("Timesheet %s notification job failed", label)
        finally:
            session.close()
