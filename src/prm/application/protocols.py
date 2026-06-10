"""Application-layer protocols (dependency inversion)."""

from datetime import date, datetime
from typing import Protocol

from prm.domain.dtos import (
    AuthToken,
    RiskSummaryContext,
    SkillMatchCandidate,
    SkillMatchContext,
    SkillMatchResult,
)
from prm.domain.entities.allocation import Allocation
from prm.domain.entities.employee import Employee
from prm.domain.entities.milestone import Milestone
from prm.domain.entities.project import Project
from prm.domain.entities.project_health_snapshot import ProjectHealthSnapshot
from prm.domain.entities.skill import EmployeeSkill, Skill
from prm.domain.entities.system_configuration import SystemConfiguration
from prm.domain.entities.timesheet import NewTimesheetEntry, TimesheetEntry, TimesheetWeek
from prm.domain.entities.user import User
from prm.domain.enums import (
    EmployeeWorkStatus,
    LLMProvider,
    MilestoneStatus,
    ProficiencyLevel,
    ProjectHealthStatus,
    ProjectStatus,
    Role,
    SkillCategory,
    UserAccountStatus,
)


class PasswordHasher(Protocol):
    def hash(self, password: str) -> str: ...

    def verify(self, password: str, password_hash: str) -> bool: ...


class LlmApiKeyProtector(Protocol):
    def encrypt(self, api_key: str) -> str: ...

    def decrypt(self, encrypted: str) -> str: ...


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
        manager_id: int | None = None,
    ) -> Employee: ...

    def set_manager_id(self, employee_id: int, *, manager_id: int | None) -> Employee: ...

    def list_by_manager_user_id(
        self,
        manager_user_id: int,
        *,
        active_only: bool = True,
    ) -> list[Employee]: ...

    def set_active(self, employee_id: int, *, is_active: bool) -> Employee: ...

    def update_utilisation_and_status(
        self,
        employee_id: int,
        *,
        current_utilisation_percent: int,
        work_status: EmployeeWorkStatus,
    ) -> Employee: ...


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
    def find_by_id(self, allocation_id: int) -> Allocation | None: ...

    def find_active_by_employee(self, employee_id: int) -> list[Allocation]: ...

    def list_by_employee(self, employee_id: int) -> list[Allocation]: ...

    def find_overlapping(
        self,
        employee_id: int,
        date_from: date,
        date_to: date | None,
        *,
        exclude_allocation_id: int | None = None,
    ) -> list[Allocation]: ...

    def list_active(
        self,
        *,
        employee_id: int | None = None,
        project_id: int | None = None,
    ) -> list[Allocation]: ...

    def list_active_for_manager(self, manager_user_id: int) -> list[Allocation]: ...

    def create(
        self,
        *,
        employee_id: int,
        project_id: int,
        utilisation_percent: int,
        from_date: date,
        to_date: date | None,
        created_by_user_id: int,
    ) -> Allocation: ...

    def end_by_id(self, allocation_id: int, *, as_of: date) -> Allocation: ...

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
        total_story_points: int = 0,
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
        total_story_points: int | None = None,
    ) -> Project: ...

    def list_by_manager_user_id(self, manager_user_id: int) -> list[Project]: ...

    def update_health(
        self,
        project_id: int,
        *,
        health_status: ProjectHealthStatus,
        health_computed_at: datetime,
    ) -> Project: ...


class ProjectHealthSnapshotRepository(Protocol):
    def find_latest_for_project(self, project_id: int) -> ProjectHealthSnapshot | None: ...

    def save(
        self,
        *,
        project_id: int,
        status: ProjectHealthStatus,
        risk_flags: tuple[str, ...],
        computed_at: datetime,
    ) -> ProjectHealthSnapshot: ...


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
        story_points: int = 0,
    ) -> Milestone: ...

    def update(
        self,
        milestone_id: int,
        *,
        title: str | None = None,
        due_date: date | None = None,
        status: MilestoneStatus | None = None,
        sequence_order: int | None = None,
        story_points: int | None = None,
    ) -> Milestone: ...

    def sum_completed_story_points(self, project_id: int) -> int: ...


class TimesheetRepository(Protocol):
    def list_recent_activity_tags(
        self,
        employee_id: int,
        *,
        weeks: int = 4,
        as_of: date | None = None,
    ) -> list[str]: ...

    def find_week_by_employee(
        self,
        employee_id: int,
        week_start_date: date,
    ) -> TimesheetWeek | None: ...

    def list_entries_for_week(self, timesheet_week_id: int) -> list[TimesheetEntry]: ...

    def list_weeks_for_employee(
        self,
        employee_id: int,
        *,
        limit: int | None = None,
    ) -> list[TimesheetWeek]: ...

    def create_week_with_entries(
        self,
        *,
        employee_id: int,
        week_start_date: date,
        total_hours: int,
        submitted_at: datetime,
        entries: tuple[NewTimesheetEntry, ...],
    ) -> TimesheetWeek: ...

    def create_missed_week(
        self,
        *,
        employee_id: int,
        week_start_date: date,
    ) -> TimesheetWeek: ...


class SystemConfigurationRepository(Protocol):
    def find_singleton(self) -> SystemConfiguration | None: ...

    def create_with_defaults(self) -> SystemConfiguration: ...

    def update(
        self,
        config_id: int,
        *,
        llm_provider: LLMProvider | None = None,
        llm_api_key_encrypted: str | None = None,
        scheduler_interval_hours: int | None = None,
        max_weekly_hours: int | None = None,
    ) -> SystemConfiguration: ...


class LLMClient(Protocol):
    """Strategy interface for LLM providers (DESIGN.md — Gemini / Groq adapters)."""

    def rank_candidates(
        self,
        context: SkillMatchContext,
        candidates: tuple[SkillMatchCandidate, ...],
    ) -> tuple[SkillMatchResult, ...]: ...

    def summarize_risk(self, context: RiskSummaryContext) -> str: ...
