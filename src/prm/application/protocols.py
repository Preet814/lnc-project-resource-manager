"""Application-layer protocols (dependency inversion)."""

from datetime import date, datetime
from typing import Protocol

from prm.domain.dtos import AuthToken
from prm.domain.entities.allocation import Allocation
from prm.domain.entities.employee import Employee
from prm.domain.entities.milestone import Milestone
from prm.domain.entities.project import Project
from prm.domain.entities.skill import EmployeeSkill, Skill
from prm.domain.entities.user import User
from prm.domain.enums import (
    EmployeeWorkStatus,
    MilestoneStatus,
    ProficiencyLevel,
    ProjectStatus,
    Role,
    SkillCategory,
    UserAccountStatus,
)


class PasswordHasher(Protocol):
    def hash(self, password: str) -> str: ...

    def verify(self, password: str, password_hash: str) -> bool: ...


class TokenPayload(Protocol):
    user_id: int
    username: str
    role: Role
    force_password_change: bool
    expires_at: datetime


class TokenService(Protocol):
    def create_access_token(
        self,
        *,
        user_id: int,
        username: str,
        role: Role,
        force_password_change: bool,
    ) -> AuthToken: ...

    def decode_access_token(self, token: str) -> TokenPayload: ...


class UserRepository(Protocol):
    def find_by_username(self, username: str) -> User | None: ...

    def find_by_id(self, user_id: int) -> User | None: ...

    def find_by_email(self, email: str) -> User | None: ...

    def list_all(self) -> list[User]: ...

    def create(
        self,
        *,
        full_name: str,
        username: str,
        email: str,
        password_hash: str,
        role: Role,
        force_password_change: bool = True,
        account_status: UserAccountStatus = UserAccountStatus.ACTIVE,
    ) -> User: ...

    def update_password(
        self,
        user_id: int,
        *,
        password_hash: str,
        force_password_change: bool,
    ) -> User: ...

    def update_account_status(
        self,
        user_id: int,
        *,
        account_status: UserAccountStatus,
    ) -> User: ...


class EmployeeRepository(Protocol):
    def find_by_id(self, employee_id: int) -> Employee | None: ...

    def find_by_user_id(self, user_id: int) -> Employee | None: ...

    def find_by_email(self, email: str) -> Employee | None: ...

    def list_all(
        self,
        *,
        work_status: EmployeeWorkStatus | None = None,
        department: str | None = None,
        active_only: bool = True,
    ) -> list[Employee]: ...

    def create(
        self,
        *,
        user_id: int,
        full_name: str,
        email: str,
        department: str,
        designation: str,
    ) -> Employee: ...

    def update(
        self,
        employee_id: int,
        *,
        full_name: str | None = None,
        email: str | None = None,
        department: str | None = None,
        designation: str | None = None,
    ) -> Employee: ...

    def set_active(self, employee_id: int, *, is_active: bool) -> Employee: ...


class SkillRepository(Protocol):
    def find_by_id(self, skill_id: int) -> Skill | None: ...

    def find_by_name(self, name: str) -> Skill | None: ...

    def create(
        self,
        *,
        name: str,
        category: SkillCategory,
        is_predefined: bool = False,
    ) -> Skill: ...

    def get_or_create(self, *, name: str, category: SkillCategory) -> Skill: ...


class EmployeeSkillRepository(Protocol):
    def list_for_employee(self, employee_id: int) -> list[EmployeeSkill]: ...

    def find_by_employee_and_skill(
        self, employee_id: int, skill_id: int
    ) -> EmployeeSkill | None: ...

    def assign(
        self,
        *,
        employee_id: int,
        skill_id: int,
        proficiency: ProficiencyLevel,
    ) -> EmployeeSkill: ...

    def update_proficiency(
        self,
        employee_skill_id: int,
        *,
        proficiency: ProficiencyLevel,
    ) -> EmployeeSkill: ...

    def remove(self, employee_skill_id: int) -> None: ...


class AllocationRepository(Protocol):
    def find_active_by_employee(self, employee_id: int) -> list[Allocation]: ...

    def list_active(
        self,
        *,
        employee_id: int | None = None,
        project_id: int | None = None,
    ) -> list[Allocation]: ...

    def end_active_for_employee(self, employee_id: int, *, as_of: date) -> list[Allocation]: ...


class ProjectRepository(Protocol):
    def find_by_id(self, project_id: int) -> Project | None: ...

    def list_all(
        self,
        *,
        status: ProjectStatus | None = None,
    ) -> list[Project]: ...

    def create(
        self,
        *,
        name: str,
        description: str | None,
        start_date: date,
        end_date: date | None,
        status: ProjectStatus,
        manager_user_id: int,
    ) -> Project: ...

    def update(
        self,
        project_id: int,
        *,
        name: str | None = None,
        description: str | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
        status: ProjectStatus | None = None,
        manager_user_id: int | None = None,
    ) -> Project: ...


class MilestoneRepository(Protocol):
    def list_for_project(self, project_id: int) -> list[Milestone]: ...

    def find_by_id(self, milestone_id: int) -> Milestone | None: ...

    def find_by_project_and_id(
        self, project_id: int, milestone_id: int
    ) -> Milestone | None: ...

    def create(
        self,
        *,
        project_id: int,
        title: str,
        due_date: date,
        status: MilestoneStatus = MilestoneStatus.NOT_STARTED,
        sequence_order: int | None = None,
    ) -> Milestone: ...

    def update(
        self,
        milestone_id: int,
        *,
        title: str | None = None,
        due_date: date | None = None,
        status: MilestoneStatus | None = None,
        sequence_order: int | None = None,
    ) -> Milestone: ...
