"""Admin employee-management use cases (BRD §3.1)."""

from datetime import date

from prm.application.protocols import (
    AllocationRepository,
    EmployeeRepository,
    UserRepository,
)
from prm.domain.dtos import EmployeeListResult, EmployeeSummary
from prm.domain.entities.employee import Employee
from prm.domain.entities.user import User
from prm.domain.enums import EmployeeWorkStatus, Role, UserAccountStatus
from prm.domain.exceptions import NotFoundError, ValidationError


class EmployeeManagementService:
    """Create, list, update, and deactivate employee work profiles."""

    def __init__(
        self,
        employee_repository: EmployeeRepository,
        user_repository: UserRepository,
        allocation_repository: AllocationRepository,
    ) -> None:
        self._employees = employee_repository
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
    ) -> Employee:
        self._require_linkable_user(user_id)

        if self._employees.find_by_user_id(user_id) is not None:
            raise ValidationError("This user already has an employee profile.")

        existing_email = self._employees.find_by_email(email)
        if existing_email is not None:
            raise ValidationError(f"Email '{email}' is already in use by another employee.")

        return self._employees.create(
            user_id=user_id,
            full_name=full_name,
            email=email,
            department=department,
            designation=designation,
        )

    def list_employees(
        self,
        *,
        work_status: EmployeeWorkStatus | None = None,
        department: str | None = None,
        active_only: bool = True,
    ) -> EmployeeListResult:
        employees = self._employees.list_all(
            work_status=work_status,
            department=department,
            active_only=active_only,
        )
        summaries = tuple(
            EmployeeSummary(
                id=employee.id,
                full_name=employee.full_name,
                department=employee.department,
                work_status=employee.work_status,
                is_active=employee.is_active,
            )
            for employee in employees
        )
        allocated_count = sum(1 for summary in summaries if summary.is_allocated())
        bench_count = sum(1 for summary in summaries if summary.is_on_bench())
        return EmployeeListResult(
            employees=summaries,
            total=len(summaries),
            allocated_count=allocated_count,
            bench_count=bench_count,
        )

    def get_employee(self, employee_id: int) -> Employee:
        return self._require_employee(employee_id)

    def update_employee(
        self,
        employee_id: int,
        *,
        full_name: str | None = None,
        email: str | None = None,
        department: str | None = None,
        designation: str | None = None,
    ) -> Employee:
        employee = self._require_employee(employee_id)
        if not employee.is_active:
            raise ValidationError(
                f"Employee '{employee.full_name}' is inactive and cannot be updated."
            )

        if email is not None:
            existing_email = self._employees.find_by_email(email)
            if existing_email is not None and existing_email.id != employee_id:
                raise ValidationError(f"Email '{email}' is already in use by another employee.")

        return self._employees.update(
            employee_id,
            full_name=full_name,
            email=email,
            department=department,
            designation=designation,
        )

    def deactivate_employee(self, employee_id: int) -> Employee:
        employee = self._require_employee(employee_id)
        if not employee.is_active:
            raise ValidationError(
                f"Employee '{employee.full_name}' is already inactive."
            )

        self._allocations.end_active_for_employee(employee_id, as_of=date.today())
        deactivated = self._employees.set_active(employee_id, is_active=False)

        if employee.user_id is not None:
            user = self._users.find_by_id(employee.user_id)
            if user is not None and user.is_active():
                self._users.update_account_status(
                    employee.user_id,
                    account_status=UserAccountStatus.INACTIVE,
                )

        return deactivated

    def assign_manager(
        self,
        *,
        employee_user_id: int,
        manager_user_id: int,
    ) -> Employee:
        """Link an employee work profile to a manager (BRD V4 §3.1.4)."""
        if employee_user_id == manager_user_id:
            raise ValidationError("An employee cannot be assigned as their own manager.")

        manager_user = self._require_manager_user(manager_user_id)
        self._require_linkable_user(employee_user_id)

        employee = self._employees.find_by_user_id(employee_user_id)
        if employee is None:
            raise NotFoundError(
                f"No employee profile found for user {employee_user_id}. "
                "Create the work profile first via POST /admin/employees."
            )
        if not employee.is_active:
            raise ValidationError(
                f"Employee '{employee.full_name}' is inactive and cannot be reassigned."
            )

        return self._employees.set_manager_id(employee.id, manager_id=manager_user.id)

    def _require_linkable_user(self, user_id: int) -> User:
        user = self._users.find_by_id(user_id)
        if user is None:
            raise NotFoundError(f"User {user_id} not found.")
        if user.role not in (Role.EMPLOYEE, Role.MANAGER):
            raise ValidationError(
                "Employee profiles can only be linked to Employee or Manager accounts."
            )
        if not user.is_active():
            raise ValidationError("Cannot link an employee profile to an inactive user account.")
        return user

    def _require_manager_user(self, user_id: int) -> User:
        user = self._users.find_by_id(user_id)
        if user is None:
            raise NotFoundError(f"User {user_id} not found.")
        if user.role != Role.MANAGER:
            raise ValidationError("Manager must be a user account with the MANAGER role.")
        if not user.is_active():
            raise ValidationError("Cannot assign employees to an inactive manager account.")
        return user

    def _require_employee(self, employee_id: int) -> Employee:
        employee = self._employees.find_by_id(employee_id)
        if employee is None:
            raise NotFoundError(f"Employee {employee_id} not found.")
        return employee
