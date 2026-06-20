"""API response models for the console HTTP client."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

from prm.domain.enums import (
    AllocationStatus,
    LLMProvider,
    MilestoneStatus,
    ProficiencyLevel,
    ProjectHealthStatus,
    ProjectStatus,
    ResourceWorkStatus,
    Role,
    SkillCategory,
    TeamGapType,
    TimesheetWeekStatus,
    UserAccountStatus,
)


@dataclass(frozen=True)
class UserSummary:
    id: int
    username: str
    full_name: str
    role: Role
    account_status: UserAccountStatus
    department: str | None = None
    designation: str | None = None


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
    designation: str
    work_status: ResourceWorkStatus
    is_active: bool
    email_verified: bool


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


@dataclass(frozen=True)
class BenchEngineer:
    user_id: int
    full_name: str
    department: str
    skill_names: tuple[str, ...]


@dataclass(frozen=True)
class ActiveEngineer:
    user_id: int
    full_name: str
    utilisation_percent: int
    availability_percent: int


@dataclass(frozen=True)
class ResourceDashboard:
    on_bench: tuple[BenchEngineer, ...]
    active: tuple[ActiveEngineer, ...]
    bench_count: int
    partial_count: int


@dataclass(frozen=True)
class EngineerAllocationDetail:
    project_name: str
    utilisation_percent: int
    from_date: date
    to_date: date | None


@dataclass(frozen=True)
class EngineerResourceDetail:
    user_id: int
    full_name: str
    department: str
    work_status: ResourceWorkStatus
    current_utilisation_percent: int
    profile_skills: tuple[str, ...]
    active_allocations: tuple[EngineerAllocationDetail, ...]
    recent_activity_tags: tuple[str, ...]


@dataclass(frozen=True)
class ManagerProjectSummary:
    project_id: int
    name: str
    end_date: date | None
    health_status: ProjectHealthStatus


@dataclass(frozen=True)
class ManagerProjectList:
    projects: tuple[ManagerProjectSummary, ...]
    total: int


@dataclass(frozen=True)
class ManagerProjectMilestone:
    milestone_id: int
    title: str
    due_date: date
    status: MilestoneStatus
    sequence_order: int
    is_overdue: bool


@dataclass(frozen=True)
class ManagerProjectResource:
    user_id: int
    user_full_name: str
    utilisation_percent: int
    from_date: date
    to_date: date | None


@dataclass(frozen=True)
class ManagerProjectDetail:
    project_id: int
    name: str
    health_status: ProjectHealthStatus
    health_computed_at: datetime | None
    risk_flags: tuple[str, ...]
    milestones: tuple[ManagerProjectMilestone, ...]
    allocated_resources: tuple[ManagerProjectResource, ...]


@dataclass(frozen=True)
class TeamTimesheetRow:
    user_id: int
    user_full_name: str
    project_id: int
    project_name: str
    hours: int
    status: TimesheetWeekStatus


@dataclass(frozen=True)
class TeamTimesheetList:
    week_start_date: date
    rows: tuple[TeamTimesheetRow, ...]
    total: int


@dataclass(frozen=True)
class EngineerTimesheetEntry:
    project_id: int
    project_name: str
    hours_worked: int
    activity_tags: tuple[str, ...]


@dataclass(frozen=True)
class EngineerTimesheetWeekDetail:
    user_id: int
    user_full_name: str
    week_start_date: date
    status: TimesheetWeekStatus
    total_hours: int
    entries: tuple[EngineerTimesheetEntry, ...]


@dataclass(frozen=True)
class SkillMatchResult:
    user_id: int
    user_name: str
    reason: str
    suggested_allocation_percent: int
    free_hours_per_week: int


@dataclass(frozen=True)
class SkillMatchList:
    project_id: int
    requirement: str
    matches: tuple[SkillMatchResult, ...]
    total: int
    message: str | None


@dataclass(frozen=True)
class RiskSummary:
    project_id: int
    summary: str
    disclaimer: str


@dataclass(frozen=True)
class TeamSlotAssignment:
    slot_id: int
    role_label: str
    position: int
    user_id: int
    user_name: str
    suggested_allocation_percent: int
    reason: str
    free_hours_per_week: int


@dataclass(frozen=True)
class TeamAvailabilityHint:
    user_name: str
    available_from: date | None


@dataclass(frozen=True)
class TeamSlotGap:
    slot_id: int
    role_label: str
    position: int
    gap_type: TeamGapType
    detail: str
    availability_hints: tuple[TeamAvailabilityHint, ...]


@dataclass(frozen=True)
class TeamMatchResult:
    project_id: int
    requirement: str
    assignments: tuple[TeamSlotAssignment, ...]
    gaps: tuple[TeamSlotGap, ...]


@dataclass(frozen=True)
class ManagerAllocation:
    allocation_id: int
    user_id: int
    project_id: int
    utilisation_percent: int
    from_date: date
    to_date: date | None
    status: AllocationStatus


@dataclass(frozen=True)
class WeekAllocationRow:
    project_id: int
    project_name: str
    utilisation_percent: int
    expected_max_hours: int


@dataclass(frozen=True)
class WeekAllocations:
    week_start_date: date
    max_weekly_hours: int
    allocations: tuple[WeekAllocationRow, ...]


@dataclass(frozen=True)
class MyAllocationRow:
    project_id: int
    project_name: str
    utilisation_percent: int
    from_date: date
    to_date: date | None
    status: AllocationStatus


@dataclass(frozen=True)
class MyAllocations:
    allocations: tuple[MyAllocationRow, ...]
    total_utilisation_percent: int


@dataclass(frozen=True)
class MyTimesheetWeekSummary:
    week_start_date: date
    total_hours: int
    status: TimesheetWeekStatus


@dataclass(frozen=True)
class MyTimesheetList:
    weeks: tuple[MyTimesheetWeekSummary, ...]
    total: int


@dataclass(frozen=True)
class MyTimesheetEntry:
    project_id: int
    project_name: str
    hours_worked: int
    activity_tags: tuple[str, ...]


@dataclass(frozen=True)
class MyTimesheetWeekDetail:
    week_start_date: date
    status: TimesheetWeekStatus
    total_hours: int
    entries: tuple[MyTimesheetEntry, ...]


@dataclass(frozen=True)
class SubmittedTimesheet:
    week_start_date: date
    status: TimesheetWeekStatus
    total_hours: int
