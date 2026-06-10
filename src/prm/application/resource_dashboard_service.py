"""Manager resource dashboard use cases (BRD §4.1)."""

from datetime import date

from prm.application.protocols import (
    AllocationRepository,
    EmployeeRepository,
    EmployeeSkillRepository,
    ProjectRepository,
    SkillRepository,
    TimesheetRepository,
)
from prm.domain.constants import MAX_UTILISATION_PERCENT
from prm.domain.dtos import (
    ActiveEmployeeSummary,
    BenchEmployeeSummary,
    EmployeeAllocationDetail,
    EmployeeResourceDetail,
    ResourceDashboardResult,
)
from prm.domain.entities.employee import Employee
from prm.domain.exceptions import NotFoundError, UnauthorizedError


class ResourceDashboardService:
    """Bench/active listings and employee drill-down for managers."""

    def __init__(
        self,
        employee_repository: EmployeeRepository,
        employee_skill_repository: EmployeeSkillRepository,
        skill_repository: SkillRepository,
        allocation_repository: AllocationRepository,
        project_repository: ProjectRepository,
        timesheet_repository: TimesheetRepository,
    ) -> None:
        self._employees = employee_repository
        self._employee_skills = employee_skill_repository
        self._skills = skill_repository
        self._allocations = allocation_repository
        self._projects = project_repository
        self._timesheets = timesheet_repository

    def get_dashboard(
        self,
        manager_user_id: int,
        *,
        as_of: date | None = None,
    ) -> ResourceDashboardResult:
        _ = as_of  # reserved for future as-of dashboard snapshots
        employees = self._employees.list_by_manager_user_id(
            manager_user_id,
            active_only=True,
        )

        on_bench: list[BenchEmployeeSummary] = []
        active: list[ActiveEmployeeSummary] = []
        partial_count = 0

        for employee in employees:
            utilisation = employee.current_utilisation_percent
            if employee.is_on_bench() or utilisation == 0:
                on_bench.append(
                    BenchEmployeeSummary(
                        employee_id=employee.id,
                        full_name=employee.full_name,
                        department=employee.department,
                        skill_names=self._skill_names(employee.id),
                    )
                )
                continue

            availability = max(0, MAX_UTILISATION_PERCENT - utilisation)
            active.append(
                ActiveEmployeeSummary(
                    employee_id=employee.id,
                    full_name=employee.full_name,
                    utilisation_percent=utilisation,
                    availability_percent=availability,
                )
            )
            if 0 < utilisation < MAX_UTILISATION_PERCENT:
                partial_count += 1

        return ResourceDashboardResult(
            on_bench=tuple(on_bench),
            active=tuple(active),
            bench_count=len(on_bench),
            partial_count=partial_count,
        )

    def get_employee_detail(
        self,
        manager_user_id: int,
        employee_id: int,
        *,
        as_of: date | None = None,
    ) -> EmployeeResourceDetail:
        reference = as_of or date.today()
        employee = self._employees.find_by_id(employee_id)
        if employee is None or not employee.is_active:
            raise NotFoundError(f"Employee {employee_id} not found.")

        self._assert_direct_team_member(manager_user_id, employee)

        allocations = self._allocations.find_active_by_employee(employee_id)
        active_allocations = tuple(
            EmployeeAllocationDetail(
                project_name=self._project_name(allocation.project_id),
                utilisation_percent=allocation.utilisation_percent,
                from_date=allocation.from_date,
                to_date=allocation.to_date,
            )
            for allocation in allocations
            if allocation.is_active_on(reference)
        )

        return EmployeeResourceDetail(
            employee_id=employee.id,
            full_name=employee.full_name,
            department=employee.department,
            work_status=employee.work_status,
            current_utilisation_percent=employee.current_utilisation_percent,
            profile_skills=self._skill_names(employee.id),
            active_allocations=active_allocations,
            recent_activity_tags=tuple(
                self._timesheets.list_recent_activity_tags(
                    employee_id,
                    weeks=4,
                    as_of=reference,
                )
            ),
        )

    @staticmethod
    def _assert_direct_team_member(manager_user_id: int, employee: Employee) -> None:
        if employee.manager_id != manager_user_id:
            raise UnauthorizedError("Employee is not assigned to your team.")

    def _skill_names(self, employee_id: int) -> tuple[str, ...]:
        assignments = self._employee_skills.list_for_employee(employee_id)
        names: list[str] = []
        for assignment in assignments:
            skill = self._skills.find_by_id(assignment.skill_id)
            if skill is not None:
                names.append(skill.name)
        return tuple(names)

    def _project_name(self, project_id: int) -> str:
        project = self._projects.find_by_id(project_id)
        if project is None:
            return "Unknown"
        return project.name
