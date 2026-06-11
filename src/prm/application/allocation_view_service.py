"""Admin allocation-view use cases (BRD §3.3)."""

from prm.application.protocols import (
    AllocationRepository,
    ProjectRepository,
    UserRepository,
)
from prm.domain.dtos import AllocationListResult, AllocationSummary
from prm.domain.entities.allocation import Allocation


class AllocationViewService:
    """Read-only company-wide allocation listing for Admin."""

    def __init__(
        self,
        allocation_repository: AllocationRepository,
        user_repository: UserRepository,
        project_repository: ProjectRepository,
    ) -> None:
        self._allocations = allocation_repository
        self._users = user_repository
        self._projects = project_repository

    def list_allocations(
        self,
        *,
        user_id: int | None = None,
        project_id: int | None = None,
    ) -> AllocationListResult:
        allocations = self._allocations.list_active(
            user_id=user_id,
            project_id=project_id,
        )
        summaries = tuple(self._to_summary(allocation) for allocation in allocations)
        return AllocationListResult(allocations=summaries, total=len(summaries))

    def _to_summary(self, allocation: Allocation) -> AllocationSummary:
        return AllocationSummary(
            allocation_id=allocation.id,
            user_id=allocation.user_id,
            user_full_name=self._user_name(allocation.user_id),
            project_id=allocation.project_id,
            project_name=self._project_name(allocation.project_id),
            utilisation_percent=allocation.utilisation_percent,
            from_date=allocation.from_date,
            to_date=allocation.to_date,
        )

    def _user_name(self, user_id: int) -> str:
        user = self._users.find_by_id(user_id)
        if user is None:
            return "Unknown"
        return user.full_name

    def _project_name(self, project_id: int) -> str:
        project = self._projects.find_by_id(project_id)
        if project is None:
            return "Unknown"
        return project.name
