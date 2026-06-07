"""Manager read-only team timesheet views (BRD §4.4)."""

from datetime import date, timedelta

from prm.application.protocols import (
    AllocationRepository,
    EmployeeRepository,
    ProjectRepository,
    TimesheetRepository,
)
from prm.domain.dtos import (
    EmployeeTimesheetEntryDetail,
    EmployeeTimesheetWeekDetail,
    TeamTimesheetListResult,
    TeamTimesheetRow,
)
from prm.domain.enums import ActivityTag, TimesheetWeekStatus
from prm.domain.exceptions import NotFoundError, UnauthorizedError


class TeamTimesheetService:
    """List and drill into team timesheets for a manager-owned project team."""

    def __init__(
        self,
        allocation_repository: AllocationRepository,
        employee_repository: EmployeeRepository,
        project_repository: ProjectRepository,
        timesheet_repository: TimesheetRepository,
    ) -> None:
        self._allocations = allocation_repository
        self._employees = employee_repository
        self._projects = project_repository
        self._timesheets = timesheet_repository

    def list_team_timesheets(
        self,
        manager_user_id: int,
        week_start_date: date,
    ) -> TeamTimesheetListResult:
        week_end = week_start_date + timedelta(days=6)
        rows: list[TeamTimesheetRow] = []

        for allocation in self._allocations.list_active_for_manager(manager_user_id):
            if not allocation.overlaps_period(week_start_date, week_end):
                continue

            hours, status = self._hours_and_status_for_project(
                allocation.employee_id,
                allocation.project_id,
                week_start_date,
            )
            rows.append(
                TeamTimesheetRow(
                    employee_id=allocation.employee_id,
                    employee_full_name=self._employee_name(allocation.employee_id),
                    project_id=allocation.project_id,
                    project_name=self._project_name(allocation.project_id),
                    hours=hours,
                    status=status,
                )
            )

        rows.sort(key=lambda row: (row.employee_full_name.lower(), row.project_name.lower()))
        return TeamTimesheetListResult(
            week_start_date=week_start_date,
            rows=tuple(rows),
            total=len(rows),
        )

    def get_employee_timesheet_detail(
        self,
        manager_user_id: int,
        employee_id: int,
        week_start_date: date,
    ) -> EmployeeTimesheetWeekDetail:
        employee = self._employees.find_by_id(employee_id)
        if employee is None:
            raise NotFoundError(f"Employee {employee_id} not found.")

        self._assert_employee_on_team(manager_user_id, employee_id, week_start_date)

        week = self._timesheets.find_week_by_employee(employee_id, week_start_date)
        if week is None:
            return EmployeeTimesheetWeekDetail(
                employee_id=employee_id,
                employee_full_name=employee.full_name,
                week_start_date=week_start_date,
                status=TimesheetWeekStatus.MISSED,
                total_hours=0,
                entries=(),
            )

        entries = tuple(
            EmployeeTimesheetEntryDetail(
                project_id=entry.project_id,
                project_name=self._project_name(entry.project_id),
                hours_worked=entry.hours_worked,
                activity_tags=tuple(
                    self._format_activity_tag(tag) for tag in entry.activity_tags
                ),
            )
            for entry in self._timesheets.list_entries_for_week(week.id)
        )
        return EmployeeTimesheetWeekDetail(
            employee_id=employee_id,
            employee_full_name=employee.full_name,
            week_start_date=week_start_date,
            status=week.status,
            total_hours=week.total_hours,
            entries=entries,
        )

    def _hours_and_status_for_project(
        self,
        employee_id: int,
        project_id: int,
        week_start_date: date,
    ) -> tuple[int, TimesheetWeekStatus]:
        week = self._timesheets.find_week_by_employee(employee_id, week_start_date)
        if week is None or week.status == TimesheetWeekStatus.MISSED:
            return 0, TimesheetWeekStatus.MISSED

        for entry in self._timesheets.list_entries_for_week(week.id):
            if entry.project_id == project_id:
                return entry.hours_worked, TimesheetWeekStatus.SUBMITTED
        return 0, TimesheetWeekStatus.SUBMITTED

    def _assert_employee_on_team(
        self,
        manager_user_id: int,
        employee_id: int,
        week_start_date: date,
    ) -> None:
        week_end = week_start_date + timedelta(days=6)
        for allocation in self._allocations.list_active_for_manager(manager_user_id):
            if allocation.employee_id != employee_id:
                continue
            if allocation.overlaps_period(week_start_date, week_end):
                return
        raise UnauthorizedError(
            "Employee is not on your project team for the selected week."
        )

    def _employee_name(self, employee_id: int) -> str:
        employee = self._employees.find_by_id(employee_id)
        if employee is None:
            return "Unknown"
        return employee.full_name

    def _project_name(self, project_id: int) -> str:
        project = self._projects.find_by_id(project_id)
        if project is None:
            return "Unknown"
        return project.name

    @staticmethod
    def _format_activity_tag(tag: ActivityTag | str) -> str:
        raw = tag.value if isinstance(tag, ActivityTag) else tag
        return raw.replace("_", " ").title()
