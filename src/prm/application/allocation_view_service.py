"""Admin allocation-view use cases (BRD §3.3)."""

from prm.application.protocols import (
    AllocationRepository,
    EmployeeRepository,
    ProjectRepository,
)
from prm.domain.dtos import AllocationListResult, AllocationSummary
from prm.domain.entities.allocation import Allocation


class AllocationViewService:
    """Read-only company-wide allocation listing for Admin."""

    def __init__(
        self,
        allocation_repository: AllocationRepository,
        employee_repository: EmployeeRepository,
        project_repository: ProjectRepository,
    ) -> None:
        self._allocations = allocation_repository
        self._employees = employee_repository
        self._projects = project_repository

    def list_allocations(
        self,
        *,
        employee_id: int | None = None,
        project_id: int | None = None,
    ) -> AllocationListResult:
        allocations = self._allocations.list_active(
            employee_id=employee_id,
            project_id=project_id,
        )
        summaries = tuple(self._to_summary(allocation) for allocation in allocations)
        return AllocationListResult(allocations=summaries, total=len(summaries))

    def _to_summary(self, allocation: Allocation) -> AllocationSummary:
        return AllocationSummary(
            allocation_id=allocation.id,
            employee_id=allocation.employee_id,
            employee_full_name=self._employee_name(allocation.employee_id),
            project_id=allocation.project_id,
            project_name=self._project_name(allocation.project_id),
            utilisation_percent=allocation.utilisation_percent,
            from_date=allocation.from_date,
            to_date=allocation.to_date,
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
