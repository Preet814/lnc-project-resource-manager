"""API response models for the console HTTP client."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

from prm.domain.enums import (
    LLMProvider,
    MilestoneStatus,
    ProficiencyLevel,
    ProjectStatus,
    ResourceWorkStatus,
    Role,
    SkillCategory,
    UserAccountStatus,
)


@dataclass(frozen=True)
class UserSummary:
    id: int
    username: str
    full_name: str
    role: Role
    account_status: UserAccountStatus


@dataclass(frozen=True)
class UserList:
    users: tuple[UserSummary, ...]
    total: int
    active_count: int
    inactive_count: int


@dataclass(frozen=True)
class EngineerSummary:
    id: int
    full_name: str
    department: str
    work_status: ResourceWorkStatus
    is_active: bool


@dataclass(frozen=True)
class EngineerList:
    engineers: tuple[EngineerSummary, ...]
    total: int
    allocated_count: int
    bench_count: int


@dataclass(frozen=True)
class EngineerDetail:
    id: int
    manager_id: int | None
    full_name: str
    email: str
    department: str
    designation: str
    work_status: ResourceWorkStatus
    is_active: bool
    current_utilisation_percent: int


@dataclass(frozen=True)
class UserSkill:
    user_skill_id: int
    skill_id: int
    skill_name: str
    category: SkillCategory
    proficiency: ProficiencyLevel


@dataclass(frozen=True)
class ProjectSummary:
    id: int
    name: str
    manager_full_name: str
    end_date: date | None
    status: ProjectStatus
    story_points_done: int
    story_points_total: int


@dataclass(frozen=True)
class ProjectList:
    projects: tuple[ProjectSummary, ...]
    total: int


@dataclass(frozen=True)
class ProjectDetail:
    id: int
    name: str
    description: str | None
    start_date: date
    end_date: date | None
    status: ProjectStatus
    manager_user_id: int
    total_story_points: int


@dataclass(frozen=True)
class Milestone:
    milestone_id: int
    title: str
    due_date: date
    status: MilestoneStatus
    sequence_order: int
    story_points: int


@dataclass(frozen=True)
class MilestoneList:
    milestones: tuple[Milestone, ...]
    total_story_points: int
    completed_story_points: int
    remaining_story_points: int


@dataclass(frozen=True)
class AllocationSummary:
    allocation_id: int
    user_id: int
    user_full_name: str
    project_id: int
    project_name: str
    utilisation_percent: int
    from_date: date
    to_date: date | None


@dataclass(frozen=True)
class AllocationList:
    allocations: tuple[AllocationSummary, ...]
    total: int


@dataclass(frozen=True)
class SystemConfig:
    llm_provider: LLMProvider
    llm_api_key_masked: str | None
    scheduler_interval_hours: int
    max_weekly_hours: int
