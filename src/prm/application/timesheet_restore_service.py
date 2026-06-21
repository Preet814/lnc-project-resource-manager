"""Manager restore of frozen timesheet submission access."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime

from prm.application.protocols import (
    EmailSender,
    TimesheetRepository,
    TimesheetSubmissionRestoreRepository,
    UserRepository,
)
from prm.application.timesheet_week_policy import is_submission_blocked
from prm.domain.constants import TIMESHEET_ENGINEER_RESTORE_SUBJECT
from prm.domain.dtos import RestoreTimesheetSubmissionResult
from prm.domain.enums import TimesheetWeekStatus
from prm.domain.exceptions import NotFoundError, UnauthorizedError, ValidationError
from prm.domain.week_calendar import assert_monday_week_start, last_completed_week_start


@dataclass(frozen=True, slots=True)
class TimesheetSubmissionAccessState:
    submission_frozen: bool
    submission_restored: bool
    can_restore: bool


class TimesheetRestoreService:
    """Restore engineer submission access after a weekly freeze."""

    def __init__(
        self,
        user_repository: UserRepository,
        timesheet_repository: TimesheetRepository,
        restore_repository: TimesheetSubmissionRestoreRepository,
        email_sender: EmailSender,
        *,
        notifications_enabled: bool = True,
        app_timezone: str = "Asia/Kolkata",
        now_provider: Callable[[], datetime] | None = None,
    ) -> None:
        self._users = user_repository
        self._timesheets = timesheet_repository
        self._restores = restore_repository
        self._email = email_sender
        self._notifications_enabled = notifications_enabled
        self._app_timezone = app_timezone
        self._now = now_provider or (lambda: datetime.now(UTC))

    def has_restore(self, user_id: int, week_start_date: date) -> bool:
        return self._restores.find_by_user_and_week(user_id, week_start_date)

    def is_submission_blocked(self, user_id: int, week_start_date: date) -> bool:
        return is_submission_blocked(
            week_start_date,
            now=self._now(),
            app_timezone=self._app_timezone,
            enabled=self._notifications_enabled,
            is_restored=self.has_restore(user_id, week_start_date),
        )

    def get_access_state(
        self,
        manager_user_id: int,
        engineer_user_id: int,
        week_start_date: date,
    ) -> TimesheetSubmissionAccessState:
        engineer = self._require_engineer(engineer_user_id)
        if week_start_date.weekday() != 0:
            return TimesheetSubmissionAccessState(
                submission_frozen=False,
                submission_restored=False,
                can_restore=False,
            )
        restored = self.has_restore(engineer_user_id, week_start_date)
        frozen = is_submission_blocked(
            week_start_date,
            now=self._now(),
            app_timezone=self._app_timezone,
            enabled=self._notifications_enabled,
            is_restored=restored,
        )
        week = self._timesheets.find_week_by_user(engineer_user_id, week_start_date)
        submitted = week is not None and week.status == TimesheetWeekStatus.SUBMITTED
        can_restore = (
            frozen
            and not restored
            and not submitted
            and engineer.manager_id == manager_user_id
        )
        return TimesheetSubmissionAccessState(
            submission_frozen=frozen,
            submission_restored=restored,
            can_restore=can_restore,
        )

    def restore_submission_access(
        self,
        manager_user_id: int,
        engineer_user_id: int,
        week_start_date: date,
    ) -> RestoreTimesheetSubmissionResult:
        engineer = self._require_engineer(engineer_user_id)
        assert_monday_week_start(week_start_date)

        if engineer.manager_id != manager_user_id:
            raise UnauthorizedError(
                "Only the employee's reporting manager can restore submission access."
            )

        last_week = last_completed_week_start(self._now().date())
        if last_week is None or week_start_date != last_week:
            raise ValidationError(
                "Submission access can only be restored for the last completed week."
            )

        state = self.get_access_state(manager_user_id, engineer_user_id, week_start_date)
        if not state.can_restore:
            if state.submission_restored:
                raise ValidationError(
                    "Submission access has already been restored for this week."
                )
            if not state.submission_frozen:
                raise ValidationError(
                    "Timesheet submission is not restricted for this week."
                )
            raise ValidationError("Submission access cannot be restored for this week.")

        restored_at = self._now()
        self._restores.create(
            user_id=engineer_user_id,
            week_start_date=week_start_date,
            restored_by_user_id=manager_user_id,
            restored_at=restored_at,
        )
        self._timesheets.delete_missed_week(engineer_user_id, week_start_date)

        if engineer.email_verified:
            self._email.send(
                to=engineer.email,
                subject=TIMESHEET_ENGINEER_RESTORE_SUBJECT,
                body=(
                    f"Hello {engineer.full_name},\n\n"
                    f"Your manager has restored timesheet submission access for the week "
                    f"starting {week_start_date.isoformat()}.\n"
                    "Please log in to the PRM console and submit your timesheet.\n"
                ),
            )

        return RestoreTimesheetSubmissionResult(
            user_id=engineer_user_id,
            week_start_date=week_start_date,
            restored_at=restored_at,
        )

    def _require_engineer(self, user_id: int):
        user = self._users.find_by_id(user_id)
        if user is None or not user.is_engineer():
            raise NotFoundError("Engineer profile not found for this user.")
        return user
