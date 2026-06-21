"""Engineer timesheet submit and history (BRD Screen 5.1, 5.2)."""

from collections.abc import Callable
from datetime import UTC, date, datetime

from prm.application.protocols import (
    AllocationRepository,
    ProjectRepository,
    SystemConfigurationRepository,
    TimesheetRepository,
    UserRepository,
)
from prm.application.timesheet_week_policy import is_last_completed_week_frozen
from prm.domain.constants import DEFAULT_APP_TIMEZONE, DEFAULT_MAX_WEEKLY_HOURS
from prm.domain.dtos import (
    MyTimesheetEntryDetail,
    MyTimesheetListResult,
    MyTimesheetWeekDetail,
    MyTimesheetWeekSummary,
    SubmittedTimesheetResult,
    SubmitTimesheetCommand,
)
from prm.domain.entities.allocation import Allocation
from prm.domain.entities.timesheet import NewTimesheetEntry
from prm.domain.entities.user import User
from prm.domain.enums import ActivityTag
from prm.domain.exceptions import NotFoundError, ValidationError
from prm.domain.week_calendar import assert_monday_week_start, week_end, week_start_on_or_before


class EngineerTimesheetService:
    """Submit and view timesheets for the logged-in engineer."""

    def __init__(
        self,
        user_repository: UserRepository,
        allocation_repository: AllocationRepository,
        project_repository: ProjectRepository,
        timesheet_repository: TimesheetRepository,
        config_repository: SystemConfigurationRepository,
        *,
        timesheet_notifications_enabled: bool = True,
        app_timezone: str = DEFAULT_APP_TIMEZONE,
        now_provider: Callable[[], datetime] | None = None,
    ) -> None:
        self._users = user_repository
        self._allocations = allocation_repository
        self._projects = project_repository
        self._timesheets = timesheet_repository
        self._config = config_repository
        self._timesheet_notifications_enabled = timesheet_notifications_enabled
        self._app_timezone = app_timezone
        self._now = now_provider or (lambda: datetime.now(UTC))

    def submit_week(
        self,
        user_id: int,
        command: SubmitTimesheetCommand,
    ) -> SubmittedTimesheetResult:
        engineer = self._require_engineer(user_id)
        week_start = command.week_start_date
        assert_monday_week_start(week_start)
        self._reject_future_week(week_start)
        self._reject_frozen_week(week_start)
        self._reject_duplicate_week(engineer.id, week_start)

        max_weekly_hours = self._max_weekly_hours()
        allocations_by_project = self._allocations_for_week(engineer.id, week_start)
        if not allocations_by_project and command.entries:
            raise ValidationError(
                "You have no active project allocations for the selected week."
            )

        seen_projects: set[int] = set()
        total_hours = 0
        new_entries: list[NewTimesheetEntry] = []

        for entry in command.entries:
            if entry.project_id in seen_projects:
                raise ValidationError(
                    f"Duplicate timesheet entry for project {entry.project_id}."
                )
            seen_projects.add(entry.project_id)

            allocation = allocations_by_project.get(entry.project_id)
            if allocation is None:
                raise ValidationError(
                    f"Project {entry.project_id} is not allocated to you for this week."
                )

            if entry.hours_worked < 0:
                raise ValidationError("Hours worked cannot be negative.")

            if entry.hours_worked > 0 and not entry.activity_tags:
                raise ValidationError(
                    f"Activity tags are required when logging hours for project "
                    f"{entry.project_id}."
                )

            expected_max = (allocation.utilisation_percent * max_weekly_hours) // 100
            if entry.hours_worked > expected_max:
                raise ValidationError(
                    f"Hours for project {entry.project_id} exceed the allocation cap "
                    f"({expected_max} hrs max for this week)."
                )

            total_hours += entry.hours_worked
            if entry.hours_worked > 0:
                new_entries.append(
                    NewTimesheetEntry(
                        project_id=entry.project_id,
                        hours_worked=entry.hours_worked,
                        activity_tags=entry.activity_tags,
                    )
                )

        if total_hours > max_weekly_hours:
            raise ValidationError(
                f"Total hours ({total_hours}) exceed the weekly maximum "
                f"({max_weekly_hours} hrs)."
            )

        submitted_at = self._now()
        week = self._timesheets.create_week_with_entries(
            user_id=engineer.id,
            week_start_date=week_start,
            total_hours=total_hours,
            submitted_at=submitted_at,
            entries=tuple(new_entries),
        )
        return SubmittedTimesheetResult(
            week_start_date=week.week_start_date,
            status=week.status,
            total_hours=week.total_hours,
            submitted_at=submitted_at,
        )

    def list_my_timesheets(self, user_id: int) -> MyTimesheetListResult:
        engineer = self._require_engineer(user_id)
        weeks = tuple(
            MyTimesheetWeekSummary(
                week_start_date=week.week_start_date,
                total_hours=week.total_hours,
                status=week.status,
            )
            for week in self._timesheets.list_weeks_for_user(engineer.id)
        )
        return MyTimesheetListResult(weeks=weeks, total=len(weeks))

    def get_my_timesheet_detail(
        self,
        user_id: int,
        week_start_date: date,
    ) -> MyTimesheetWeekDetail:
        engineer = self._require_engineer(user_id)
        assert_monday_week_start(week_start_date)

        week = self._timesheets.find_week_by_user(engineer.id, week_start_date)
        if week is None:
            raise NotFoundError(
                f"No timesheet found for week starting {week_start_date.isoformat()}."
            )

        entries = tuple(
            MyTimesheetEntryDetail(
                project_id=entry.project_id,
                project_name=self._project_name(entry.project_id),
                hours_worked=entry.hours_worked,
                activity_tags=tuple(
                    self._format_activity_tag(tag) for tag in entry.activity_tags
                ),
            )
            for entry in self._timesheets.list_entries_for_week(week.id)
        )
        return MyTimesheetWeekDetail(
            week_start_date=week.week_start_date,
            status=week.status,
            total_hours=week.total_hours,
            entries=entries,
        )

    def _require_engineer(self, user_id: int) -> User:
        user = self._users.find_by_id(user_id)
        if user is None or not user.is_engineer():
            raise NotFoundError("Engineer profile not found for this user.")
        return user

    def _max_weekly_hours(self) -> int:
        config = self._config.find_singleton()
        if config is None:
            return DEFAULT_MAX_WEEKLY_HOURS
        return config.get_max_weekly_hours()

    def _allocations_for_week(
        self,
        user_id: int,
        week_start: date,
    ) -> dict[int, Allocation]:
        period_end = week_end(week_start)
        allocations = {
            allocation.project_id: allocation
            for allocation in self._allocations.find_active_by_user(user_id)
            if allocation.overlaps_period(week_start, period_end)
        }
        return allocations

    @staticmethod
    def _reject_future_week(week_start: date) -> None:
        current_week_start = week_start_on_or_before(date.today())
        if week_start > current_week_start:
            raise ValidationError("Cannot submit a timesheet for a future week.")

    def _reject_frozen_week(self, week_start: date) -> None:
        if is_last_completed_week_frozen(
            week_start,
            now=self._now(),
            app_timezone=self._app_timezone,
            enabled=self._timesheet_notifications_enabled,
        ):
            raise ValidationError(
                "Timesheet submission for this week is closed after Tuesday 17:30 IST."
            )

    def _reject_duplicate_week(self, user_id: int, week_start: date) -> None:
        existing = self._timesheets.find_week_by_user(user_id, week_start)
        if existing is not None:
            raise ValidationError(
                f"A timesheet for week starting {week_start.isoformat()} already exists."
            )

    def _project_name(self, project_id: int) -> str:
        project = self._projects.find_by_id(project_id)
        if project is None:
            return "Unknown"
        return project.name

    @staticmethod
    def _format_activity_tag(tag: ActivityTag | str) -> str:
        raw = tag.value if isinstance(tag, ActivityTag) else tag
        return raw.replace("_", " ").title()
