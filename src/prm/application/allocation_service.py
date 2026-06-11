"""Manager direct allocate and end allocation use cases (BRD §4.2)."""

from datetime import date

from prm.application.authorization_service import AuthorizationService
from prm.application.protocols import (
    AllocationRepository,
    ProjectRepository,
    UserRepository,
)
from prm.application.utilisation_calculator import UtilisationCalculator
from prm.domain.dtos import AllocationSummary
from prm.domain.entities.allocation import Allocation
from prm.domain.entities.user import User
from prm.domain.enums import ResourceWorkStatus
from prm.domain.exceptions import ConflictError, NotFoundError, UnauthorizedError, ValidationError


class AllocationService:
    """Create and end allocations; enforce ownership and utilisation rules."""

    def __init__(
        self,
        allocation_repository: AllocationRepository,
        user_repository: UserRepository,
        project_repository: ProjectRepository,
        authorization: AuthorizationService,
        utilisation: UtilisationCalculator,
    ) -> None:
        self._allocations = allocation_repository
        self._users = user_repository
        self._projects = project_repository
        self._authorization = authorization
        self._utilisation = utilisation

    def allocate_direct(
        self,
        manager_user_id: int,
        *,
        project_id: int,
        user_id: int,
        utilisation_percent: int,
        from_date: date,
        to_date: date | None,
    ) -> Allocation:
        project = self._authorization.assert_can_allocate(manager_user_id, project_id)
        if not project.allows_allocation():
            raise ValidationError(
                "Project must be ACTIVE or PLANNED to accept allocations."
            )

        self._require_active_engineer(user_id, manager_user_id=manager_user_id)

        validation = self._utilisation.validate_new_allocation(
            user_id,
            utilisation_percent,
            from_date,
            to_date,
        )
        if not validation.is_valid:
            raise ConflictError(validation.message)

        allocation = self._allocations.create(
            user_id=user_id,
            project_id=project_id,
            utilisation_percent=utilisation_percent,
            from_date=from_date,
            to_date=to_date,
            created_by_user_id=manager_user_id,
        )
        self._sync_user_utilisation(user_id, from_date)
        return allocation

    def end_allocation(
        self,
        manager_user_id: int,
        allocation_id: int,
        *,
        as_of: date | None = None,
    ) -> Allocation:
        allocation = self._require_active_allocation(allocation_id)
        self._authorization.assert_can_allocate(manager_user_id, allocation.project_id)

        end_date = as_of or date.today()
        ended = self._allocations.end_by_id(allocation_id, as_of=end_date)
        self._sync_user_utilisation(ended.user_id, end_date)
        return ended

    def list_project_allocations(
        self,
        manager_user_id: int,
        project_id: int,
    ) -> tuple[AllocationSummary, ...]:
        self._authorization.assert_can_allocate(manager_user_id, project_id)
        allocations = self._allocations.list_active(project_id=project_id)
        return tuple(self._to_summary(allocation) for allocation in allocations)

    def _sync_user_utilisation(self, user_id: int, as_of: date) -> None:
        utilisation = self._utilisation.compute_utilisation_on(user_id, as_of)
        work_status = (
            ResourceWorkStatus.BENCH
            if utilisation == 0
            else ResourceWorkStatus.ALLOCATED
        )
        self._users.update_resource_status(
            user_id,
            utilisation_percent=utilisation,
            work_status=work_status,
        )

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

    def _require_active_engineer(
        self,
        user_id: int,
        *,
        manager_user_id: int,
    ) -> User:
        user = self._users.find_by_id(user_id)
        if user is None or not user.is_active():
            raise NotFoundError(f"Engineer {user_id} not found.")
        if user.manager_id != manager_user_id:
            raise UnauthorizedError("Engineer is not assigned to your team.")
        return user

    def _require_active_allocation(self, allocation_id: int) -> Allocation:
        allocation = self._allocations.find_by_id(allocation_id)
        if allocation is None:
            raise NotFoundError(f"Allocation {allocation_id} not found.")
        return allocation
