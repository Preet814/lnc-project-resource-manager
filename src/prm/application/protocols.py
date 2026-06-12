"""Application-layer protocols (dependency inversion)."""

from datetime import date, datetime
from typing import Protocol

from prm.domain.dtos import (
    AuthToken,
    RiskSummaryContext,
    SkillMatchCandidate,
    SkillMatchContext,
    SkillMatchResult,
    TeamAssignmentExplainContext,
    TeamAssignmentReason,
    TeamPlan,
    TeamPlanParseContext,
)
from prm.domain.entities.allocation import Allocation
from prm.domain.entities.milestone import Milestone
from prm.domain.entities.project import Project
from prm.domain.entities.project_health_snapshot import ProjectHealthSnapshot
from prm.domain.entities.skill import Skill, UserSkill
from prm.domain.entities.system_configuration import SystemConfiguration
from prm.domain.entities.timesheet import NewTimesheetEntry, TimesheetEntry, TimesheetWeek
from prm.domain.entities.user import User
from prm.domain.enums import (
    LLMProvider,
    MilestoneStatus,
    ProficiencyLevel,
    ProjectHealthStatus,
    ProjectStatus,
    ResourceWorkStatus,
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

    def list_engineers(
        self,
        *,
        work_status: ResourceWorkStatus | None = None,
        department_id: int | None = None,
        active_only: bool = True,
    ) -> list[User]: ...

    def list_by_manager_id(
        self,
        manager_id: int,
        *,
        active_only: bool = True,
        engineers_only: bool = True,
    ) -> list[User]: ...

    def create(
        self,
        *,
        full_name: str,
        username: str,
        email: str,
        password_hash: str,
        role_id: int,
        department_id: int | None = None,
        designation_id: int | None = None,
        manager_id: int | None = None,
        force_password_change: bool = True,
        account_status: UserAccountStatus = UserAccountStatus.ACTIVE,
    ) -> User: ...

    def update_profile(
        self,
        user_id: int,
        *,
        full_name: str | None = None,
        email: str | None = None,
        department_id: int | None = None,
        designation_id: int | None = None,
        manager_id: int | None = None,
    ) -> User: ...

    def set_manager_id(self, user_id: int, *, manager_id: int | None) -> User: ...

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

    def update_resource_status(
        self,
        user_id: int,
        *,
        utilisation_percent: int,
        work_status: ResourceWorkStatus,
    ) -> User: ...

    def resolve_role_id(self, role: Role) -> int: ...

    def resolve_department_id(self, name: str) -> int | None: ...

    def resolve_designation_id(self, name: str) -> int | None: ...


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


class UserSkillRepository(Protocol):
    def list_for_user(self, user_id: int) -> list[UserSkill]: ...

    def find_by_user_and_skill(self, user_id: int, skill_id: int) -> UserSkill | None: ...

    def assign(
        self,
        *,
        user_id: int,
        skill_id: int,
        proficiency: ProficiencyLevel,
    ) -> UserSkill: ...

    def update_proficiency(
        self,
        user_skill_id: int,
        *,
        proficiency: ProficiencyLevel,
    ) -> UserSkill: ...

    def remove(self, user_skill_id: int) -> None: ...


class AllocationRepository(Protocol):
    def find_by_id(self, allocation_id: int) -> Allocation | None: ...

    def find_active_by_user(self, user_id: int) -> list[Allocation]: ...

    def list_by_user(self, user_id: int) -> list[Allocation]: ...

    def find_overlapping(
        self,
        user_id: int,
        date_from: date,
        date_to: date | None,
        *,
        exclude_allocation_id: int | None = None,
    ) -> list[Allocation]: ...

    def list_active(
        self,
        *,
        user_id: int | None = None,
        project_id: int | None = None,
    ) -> list[Allocation]: ...

    def list_active_for_manager(self, manager_user_id: int) -> list[Allocation]: ...

    def create(
        self,
        *,
        user_id: int,
        project_id: int,
        utilisation_percent: int,
        from_date: date,
        to_date: date | None,
        created_by_user_id: int,
    ) -> Allocation: ...

    def end_by_id(self, allocation_id: int, *, as_of: date) -> Allocation: ...

    def end_active_for_user(self, user_id: int, *, as_of: date) -> list[Allocation]: ...


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
        user_id: int,
        *,
        weeks: int = 4,
        as_of: date | None = None,
    ) -> list[str]: ...

    def find_week_by_user(
        self,
        user_id: int,
        week_start_date: date,
    ) -> TimesheetWeek | None: ...

    def list_entries_for_week(self, timesheet_week_id: int) -> list[TimesheetEntry]: ...

    def list_weeks_for_user(
        self,
        user_id: int,
        *,
        limit: int | None = None,
    ) -> list[TimesheetWeek]: ...

    def create_week_with_entries(
        self,
        *,
        user_id: int,
        week_start_date: date,
        total_hours: int,
        submitted_at: datetime,
        entries: tuple[NewTimesheetEntry, ...],
    ) -> TimesheetWeek: ...

    def create_missed_week(
        self,
        *,
        user_id: int,
        week_start_date: date,
    ) -> TimesheetWeek: ...


class PermissionRepository(Protocol):
    def list_codes_for_role(self, role_id: int) -> frozenset[str]: ...


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

    def parse_team_plan(self, context: TeamPlanParseContext) -> TeamPlan: ...

    def explain_team_assignments(
        self,
        context: TeamAssignmentExplainContext,
    ) -> tuple[TeamAssignmentReason, ...]: ...
