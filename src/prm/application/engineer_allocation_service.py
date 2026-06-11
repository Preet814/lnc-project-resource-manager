"""Engineer allocation views for timesheet submit and history (BRD Screen 5.1, 5.3)."""

from datetime import date

from prm.application.protocols import (
    AllocationRepository,
    ProjectRepository,
    SystemConfigurationRepository,
    UserRepository,
)
from prm.domain.constants import DEFAULT_MAX_WEEKLY_HOURS
from prm.domain.dtos import (
    MyAllocationRow,
    MyAllocationsResult,
    WeekAllocationRow,
    WeekAllocationsResult,
)
from prm.domain.entities.user import User
from prm.domain.exceptions import NotFoundError
from prm.domain.week_calendar import assert_monday_week_start, week_end


class EngineerAllocationService:
    """Read-only allocation views for the logged-in engineer."""

    def __init__(
        self,
        user_repository: UserRepository,
        allocation_repository: AllocationRepository,
        project_repository: ProjectRepository,
        config_repository: SystemConfigurationRepository,
    ) -> None:
        self._users = user_repository
        self._allocations = allocation_repository
        self._projects = project_repository
        self._config = config_repository

    def list_allocations_for_week(
        self,
        user_id: int,
        week_start_date: date,
    ) -> WeekAllocationsResult:
        engineer = self._require_engineer(user_id)
        assert_monday_week_start(week_start_date)

        max_weekly_hours = self._max_weekly_hours()
        period_end = week_end(week_start_date)
        rows: list[WeekAllocationRow] = []

        for allocation in self._allocations.find_active_by_user(engineer.id):
            if not allocation.overlaps_period(week_start_date, period_end):
                continue
            rows.append(
                WeekAllocationRow(
                    project_id=allocation.project_id,
                    project_name=self._project_name(allocation.project_id),
                    utilisation_percent=allocation.utilisation_percent,
                    expected_max_hours=(
                        allocation.utilisation_percent * max_weekly_hours
                    ) // 100,
                )
            )

        rows.sort(key=lambda row: row.project_name.lower())
        return WeekAllocationsResult(
            week_start_date=week_start_date,
            max_weekly_hours=max_weekly_hours,
            allocations=tuple(rows),
        )

    def list_my_allocations(self, user_id: int) -> MyAllocationsResult:
        engineer = self._require_engineer(user_id)
        rows: list[MyAllocationRow] = []
        total_utilisation = 0

        for allocation in self._allocations.find_active_by_user(engineer.id):
            rows.append(
                MyAllocationRow(
                    project_id=allocation.project_id,
                    project_name=self._project_name(allocation.project_id),
                    utilisation_percent=allocation.utilisation_percent,
                    from_date=allocation.from_date,
                    to_date=allocation.to_date,
                    status=allocation.status,
                )
            )
            total_utilisation += allocation.utilisation_percent

        rows.sort(key=lambda row: row.project_name.lower())
        return MyAllocationsResult(
            allocations=tuple(rows),
            total_utilisation_percent=total_utilisation,
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

    def _project_name(self, project_id: int) -> str:
        project = self._projects.find_by_id(project_id)
        if project is None:
            return "Unknown"
        return project.name
