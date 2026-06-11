"""Admin engineer-profile use cases (BRD §3.1)."""

from datetime import date

from prm.application.protocols import AllocationRepository, UserRepository
from prm.domain.dtos import EngineerListResult, EngineerSummary
from prm.domain.entities.user import User
from prm.domain.enums import ResourceWorkStatus, Role, UserAccountStatus
from prm.domain.exceptions import NotFoundError, ValidationError


class UserProfileService:
    """Create, list, update, and deactivate engineer work profiles."""

    def __init__(
        self,
        user_repository: UserRepository,
        allocation_repository: AllocationRepository,
    ) -> None:
        self._users = user_repository
        self._allocations = allocation_repository

    def create_employee(
        self,
        *,
        user_id: int,
        full_name: str,
        email: str,
        department: str,
        designation: str,
    ) -> User:
        self._require_profile_user(user_id)

        existing_email = self._users.find_by_email(email)
        if existing_email is not None and existing_email.id != user_id:
            raise ValidationError(f"Email '{email}' is already in use by another user.")

        department_id = self._require_department_id(department)
        designation_id = self._require_designation_id(designation)

        return self._users.update_profile(
            user_id,
            full_name=full_name,
            email=email,
            department_id=department_id,
            designation_id=designation_id,
        )

    def list_employees(
        self,
        *,
        work_status: ResourceWorkStatus | None = None,
        department: str | None = None,
        active_only: bool = True,
    ) -> EngineerListResult:
        department_id = (
            self._users.resolve_department_id(department) if department is not None else None
        )
        engineers = self._users.list_engineers(
            work_status=work_status,
            department_id=department_id,
            active_only=active_only,
        )
        summaries = tuple(
            EngineerSummary(
                id=engineer.id,
                full_name=engineer.full_name,
                department=engineer.department_name or "",
                designation=engineer.designation_name or "",
                work_status=engineer.work_status or ResourceWorkStatus.BENCH,
                is_active=engineer.is_active(),
            )
            for engineer in engineers
        )
        allocated_count = sum(1 for summary in summaries if summary.is_allocated())
        bench_count = sum(1 for summary in summaries if summary.is_on_bench())
        return EngineerListResult(
            engineers=summaries,
            total=len(summaries),
            allocated_count=allocated_count,
            bench_count=bench_count,
        )

    def get_employee(self, user_id: int) -> User:
        return self._require_engineer(user_id)

    def update_employee(
        self,
        user_id: int,
        *,
        full_name: str | None = None,
        email: str | None = None,
        department: str | None = None,
        designation: str | None = None,
    ) -> User:
        engineer = self._require_engineer(user_id)
        if not engineer.is_active():
            raise ValidationError(
                f"User '{engineer.full_name}' is inactive and cannot be updated."
            )

        if email is not None:
            existing_email = self._users.find_by_email(email)
            if existing_email is not None and existing_email.id != user_id:
                raise ValidationError(f"Email '{email}' is already in use by another user.")

        department_id = (
            self._require_department_id(department) if department is not None else None
        )
        designation_id = (
            self._require_designation_id(designation) if designation is not None else None
        )

        return self._users.update_profile(
            user_id,
            full_name=full_name,
            email=email,
            department_id=department_id,
            designation_id=designation_id,
        )

    def deactivate_employee(self, user_id: int) -> User:
        engineer = self._require_engineer(user_id)
        if not engineer.is_active():
            raise ValidationError(f"User '{engineer.full_name}' is already inactive.")

        self._allocations.end_active_for_user(user_id, as_of=date.today())
        return self._users.update_account_status(
            user_id,
            account_status=UserAccountStatus.INACTIVE,
        )

    def assign_manager(
        self,
        *,
        engineer_user_id: int,
        manager_user_id: int,
    ) -> User:
        """Link an engineer to a manager (BRD V4 §3.1.4)."""
        if engineer_user_id == manager_user_id:
            raise ValidationError("An engineer cannot be assigned as their own manager.")

        manager_user = self._require_manager_user(manager_user_id)
        engineer = self._require_engineer(engineer_user_id)
        if not engineer.is_active():
            raise ValidationError(
                f"User '{engineer.full_name}' is inactive and cannot be reassigned."
            )

        return self._users.set_manager_id(engineer.id, manager_id=manager_user.id)

    def _require_profile_user(self, user_id: int) -> User:
        user = self._users.find_by_id(user_id)
        if user is None:
            raise NotFoundError(f"User {user_id} not found.")
        if user.role not in (Role.ENGINEER, Role.MANAGER):
            raise ValidationError(
                "Engineer profiles can only be linked to Engineer or Manager accounts."
            )
        if not user.is_active():
            raise ValidationError("Cannot link an engineer profile to an inactive user account.")
        return user

    def _require_engineer(self, user_id: int) -> User:
        user = self._users.find_by_id(user_id)
        if user is None or not user.is_engineer():
            raise NotFoundError(f"Engineer {user_id} not found.")
        return user

    def _require_manager_user(self, user_id: int) -> User:
        user = self._users.find_by_id(user_id)
        if user is None:
            raise NotFoundError(f"User {user_id} not found.")
        if user.role != Role.MANAGER:
            raise ValidationError("Manager must be a user account with the MANAGER role.")
        if not user.is_active():
            raise ValidationError("Cannot assign engineers to an inactive manager account.")
        return user

    def _require_department_id(self, name: str) -> int:
        department_id = self._users.resolve_department_id(name)
        if department_id is None:
            raise ValidationError(f"Department '{name}' not found.")
        return department_id

    def _require_designation_id(self, name: str) -> int:
        designation_id = self._users.resolve_designation_id(name)
        if designation_id is None:
            raise ValidationError(f"Designation '{name}' not found.")
        return designation_id
