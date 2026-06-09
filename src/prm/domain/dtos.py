"""Data transfer objects returned across application boundaries."""

from dataclasses import dataclass
from datetime import UTC, date, datetime

from prm.domain.enums import (
    ActivityTag,
    AllocationStatus,
    EmployeeWorkStatus,
    LLMProvider,
    MilestoneStatus,
    ProficiencyLevel,
    ProjectHealthStatus,
    ProjectStatus,
    Role,
    SkillCategory,
    TimesheetWeekStatus,
    UserAccountStatus,
)


@dataclass(frozen=True, slots=True)
class AuthToken:
    """Login outcome — JWT access token and metadata (class diagram «DTO»)."""

    token: str
    user_id: int
    expires_at: datetime

    def is_valid(self, now: datetime | None = None) -> bool:
        reference = now or datetime.now(UTC)
        expires = self.expires_at
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=UTC)
        if reference.tzinfo is None:
            reference = reference.replace(tzinfo=UTC)
        return reference < expires


@dataclass(frozen=True, slots=True)
class LoginResult:
    """Successful login — token plus flags the console needs for routing."""

    access_token: str
    token_type: str
    user_id: int
    username: str
    full_name: str
    role: Role
    force_password_change: bool
    expires_at: datetime


@dataclass(frozen=True, slots=True)
class UserSummary:
    """Compact user row for admin list screens (BRD §3.4.2)."""

    id: int
    username: str
    full_name: str
    role: Role
    account_status: UserAccountStatus

    def is_active(self) -> bool:
        return self.account_status == UserAccountStatus.ACTIVE


@dataclass(frozen=True, slots=True)
class UserListResult:
    """All users plus aggregate counts for the admin dashboard."""

    users: tuple[UserSummary, ...]
    total: int
    active_count: int
    inactive_count: int


@dataclass(frozen=True, slots=True)
class EmployeeSummary:
    """Compact employee row for admin list screens (BRD §3.1.2)."""

    id: int
    full_name: str
    department: str
    work_status: EmployeeWorkStatus
    is_active: bool

    def is_on_bench(self) -> bool:
        return self.work_status == EmployeeWorkStatus.BENCH

    def is_allocated(self) -> bool:
        return self.work_status == EmployeeWorkStatus.ALLOCATED


@dataclass(frozen=True, slots=True)
class EmployeeListResult:
    """All employees plus bench/allocated counts for the admin dashboard."""

    employees: tuple[EmployeeSummary, ...]
    total: int
    allocated_count: int
    bench_count: int


@dataclass(frozen=True, slots=True)
class EmployeeSkillDetail:
    """Skill row for admin manage-skills screen (BRD §3.1.4)."""

    employee_skill_id: int
    skill_id: int
    skill_name: str
    category: SkillCategory
    proficiency: ProficiencyLevel
    assigned_at: datetime


@dataclass(frozen=True, slots=True)
class ProjectSummary:
    """Compact project row for admin list screen (BRD §3.2.2)."""

    id: int
    name: str
    manager_full_name: str
    end_date: date | None
    status: ProjectStatus


@dataclass(frozen=True, slots=True)
class ProjectListResult:
    """All projects plus status counts for the admin dashboard."""

    projects: tuple[ProjectSummary, ...]
    total: int
    active_count: int
    planned_count: int
    on_hold_count: int


@dataclass(frozen=True, slots=True)
class MilestoneDetail:
    """Milestone row for admin manage-milestones screen (BRD §3.2.3)."""

    milestone_id: int
    title: str
    due_date: date
    status: MilestoneStatus
    sequence_order: int


@dataclass(frozen=True, slots=True)
class AllocationSummary:
    """Active allocation row for admin view-all screen (BRD §3.3)."""

    allocation_id: int
    employee_id: int
    employee_full_name: str
    project_id: int
    project_name: str
    utilisation_percent: int
    from_date: date
    to_date: date | None


@dataclass(frozen=True, slots=True)
class AllocationListResult:
    """All active allocations plus total count for the admin dashboard."""

    allocations: tuple[AllocationSummary, ...]
    total: int


@dataclass(frozen=True, slots=True)
class SystemConfigurationSummary:
    """Current system settings for admin configuration screen (BRD §3.5)."""

    llm_provider: LLMProvider
    llm_api_key_masked: str | None
    scheduler_interval_hours: int
    max_weekly_hours: int


@dataclass(frozen=True, slots=True)
class ValidationResult:
    """Outcome of a business-rule check (utilisation cap, date range, etc.)."""

    is_valid: bool
    message: str
    total_percent: int | None = None


@dataclass(frozen=True, slots=True)
class BenchEmployeeSummary:
    """Bench row for manager resource dashboard (BRD §4.1)."""

    employee_id: int
    full_name: str
    department: str
    skill_names: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ActiveEmployeeSummary:
    """Allocated employee row for manager resource dashboard (BRD §4.1)."""

    employee_id: int
    full_name: str
    utilisation_percent: int
    availability_percent: int


@dataclass(frozen=True, slots=True)
class ResourceDashboardResult:
    """Manager resource dashboard aggregates (BRD §4.1)."""

    on_bench: tuple[BenchEmployeeSummary, ...]
    active: tuple[ActiveEmployeeSummary, ...]
    bench_count: int
    over_utilised_count: int
    partial_count: int


@dataclass(frozen=True, slots=True)
class EmployeeAllocationDetail:
    """Active allocation row in employee drill-down (BRD §4.1)."""

    project_name: str
    utilisation_percent: int
    from_date: date
    to_date: date | None


@dataclass(frozen=True, slots=True)
class EmployeeResourceDetail:
    """Employee drill-down for manager resource dashboard (BRD §4.1)."""

    employee_id: int
    full_name: str
    department: str
    work_status: EmployeeWorkStatus
    current_utilisation_percent: int
    profile_skills: tuple[str, ...]
    active_allocations: tuple[EmployeeAllocationDetail, ...]
    recent_activity_tags: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ManagerProjectSummary:
    """Compact project row for manager My Projects screen (BRD §4.3)."""

    project_id: int
    name: str
    end_date: date | None
    health_status: ProjectHealthStatus


@dataclass(frozen=True, slots=True)
class ManagerProjectListResult:
    """Projects owned by the logged-in manager."""

    projects: tuple[ManagerProjectSummary, ...]
    total: int


@dataclass(frozen=True, slots=True)
class ManagerProjectMilestoneRow:
    """Milestone row in manager project detail (BRD §4.3)."""

    milestone_id: int
    title: str
    due_date: date
    status: MilestoneStatus
    sequence_order: int
    is_overdue: bool


@dataclass(frozen=True, slots=True)
class ManagerProjectResourceRow:
    """Allocated resource row in manager project detail (BRD §4.3)."""

    employee_id: int
    employee_full_name: str
    utilisation_percent: int
    from_date: date
    to_date: date | None


@dataclass(frozen=True, slots=True)
class ManagerProjectDetail:
    """Project health detail for manager (BRD §4.3)."""

    project_id: int
    name: str
    health_status: ProjectHealthStatus
    health_computed_at: datetime | None
    risk_flags: tuple[str, ...]
    milestones: tuple[ManagerProjectMilestoneRow, ...]
    allocated_resources: tuple[ManagerProjectResourceRow, ...]


@dataclass(frozen=True, slots=True)
class TeamTimesheetRow:
    """One employee/project line on manager team timesheets (BRD §4.4)."""

    employee_id: int
    employee_full_name: str
    project_id: int
    project_name: str
    hours: int
    status: TimesheetWeekStatus


@dataclass(frozen=True, slots=True)
class TeamTimesheetListResult:
    """Team timesheet rows for a selected week (BRD §4.4)."""

    week_start_date: date
    rows: tuple[TeamTimesheetRow, ...]
    total: int


@dataclass(frozen=True, slots=True)
class EmployeeTimesheetEntryDetail:
    """Project line within an employee's weekly timesheet detail."""

    project_id: int
    project_name: str
    hours_worked: int
    activity_tags: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class EmployeeTimesheetWeekDetail:
    """Employee timesheet drill-down for manager (BRD §4.4)."""

    employee_id: int
    employee_full_name: str
    week_start_date: date
    status: TimesheetWeekStatus
    total_hours: int
    entries: tuple[EmployeeTimesheetEntryDetail, ...]


@dataclass(frozen=True, slots=True)
class SubmitTimesheetEntry:
    """One project line in an employee timesheet submission (BRD Screen 5.1)."""

    project_id: int
    hours_worked: int
    activity_tags: tuple[ActivityTag, ...]


@dataclass(frozen=True, slots=True)
class SubmitTimesheetCommand:
    """Employee weekly timesheet submission payload."""

    week_start_date: date
    entries: tuple[SubmitTimesheetEntry, ...]


@dataclass(frozen=True, slots=True)
class SubmittedTimesheetResult:
    """Outcome after a successful timesheet submission."""

    week_start_date: date
    status: TimesheetWeekStatus
    total_hours: int
    submitted_at: datetime


@dataclass(frozen=True, slots=True)
class WeekAllocationRow:
    """Active allocation row for timesheet submit context (BRD Screen 5.1)."""

    project_id: int
    project_name: str
    utilisation_percent: int
    expected_max_hours: int


@dataclass(frozen=True, slots=True)
class WeekAllocationsResult:
    """Allocations available for logging hours in a selected week."""

    week_start_date: date
    max_weekly_hours: int
    allocations: tuple[WeekAllocationRow, ...]


@dataclass(frozen=True, slots=True)
class MyAllocationRow:
    """Employee's allocation row for My Allocations screen (BRD Screen 5.3)."""

    project_id: int
    project_name: str
    utilisation_percent: int
    from_date: date
    to_date: date | None
    status: AllocationStatus


@dataclass(frozen=True, slots=True)
class MyAllocationsResult:
    """Employee allocation history for My Allocations screen."""

    allocations: tuple[MyAllocationRow, ...]
    total_utilisation_percent: int


@dataclass(frozen=True, slots=True)
class MyTimesheetWeekSummary:
    """Compact row for employee timesheet history (BRD Screen 5.2)."""

    week_start_date: date
    total_hours: int
    status: TimesheetWeekStatus


@dataclass(frozen=True, slots=True)
class MyTimesheetListResult:
    """Submitted timesheet weeks for the logged-in employee."""

    weeks: tuple[MyTimesheetWeekSummary, ...]
    total: int


@dataclass(frozen=True, slots=True)
class MyTimesheetEntryDetail:
    """Project line in employee's own timesheet week detail."""

    project_id: int
    project_name: str
    hours_worked: int
    activity_tags: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class MyTimesheetWeekDetail:
    """Employee timesheet drill-down for own history (BRD Screen 5.2)."""

    week_start_date: date
    status: TimesheetWeekStatus
    total_hours: int
    entries: tuple[MyTimesheetEntryDetail, ...]


@dataclass(frozen=True, slots=True)
class SkillMatchCandidate:
    """Pre-filtered employee facts sent to the LLM for ranking (BRD §4.2 AI, §4.5)."""

    employee_id: int
    full_name: str
    skill_names: tuple[str, ...]
    utilisation_percent: int
    free_hours_per_week: int
    recent_activity_tags: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class SkillMatchContext:
    """Project and requirement context for LLM skill matching (class diagram «DTO»)."""

    project_id: int
    project_name: str
    requirement: str
    requested_hours_per_week: int | None


@dataclass(frozen=True, slots=True)
class SkillMatchResult:
    """Ranked AI suggestion for one employee (class diagram «DTO»)."""

    employee_id: int
    employee_name: str
    reason: str
    suggested_allocation_percent: int
    free_hours_per_week: int


@dataclass(frozen=True, slots=True)
class SkillMatchListResult:
    """Skill match outcome for a project requirement (BRD §4.2 AI, §4.5)."""

    project_id: int
    requirement: str
    matches: tuple[SkillMatchResult, ...]
    total: int
    message: str | None = None


@dataclass(frozen=True, slots=True)
class RiskSummaryMilestoneFact:
    """Milestone fact included in risk summary LLM context."""

    title: str
    due_date: date
    status: MilestoneStatus
    is_overdue: bool


@dataclass(frozen=True, slots=True)
class RiskSummaryResourceFact:
    """Allocation fact included in risk summary LLM context."""

    employee_full_name: str
    utilisation_percent: int


@dataclass(frozen=True, slots=True)
class RiskSummaryTimesheetFact:
    """Recent hours fact included in risk summary LLM context."""

    employee_full_name: str
    week_start_date: date
    hours_logged: int
    expected_hours: int


@dataclass(frozen=True, slots=True)
class RiskSummaryContext:
    """Factual project data passed to the LLM for risk narrative (BRD §4.3 [A], §4.5)."""

    project_id: int
    project_name: str
    health_status: ProjectHealthStatus
    end_date: date | None
    risk_flags: tuple[str, ...]
    milestones: tuple[RiskSummaryMilestoneFact, ...]
    allocated_resources: tuple[RiskSummaryResourceFact, ...]
    recent_timesheets: tuple[RiskSummaryTimesheetFact, ...]


@dataclass(frozen=True, slots=True)
class RiskSummaryResult:
    """AI risk narrative for a manager-owned project."""

    project_id: int
    summary: str
    disclaimer: str


@dataclass(frozen=True, slots=True)
class HealthMilestoneFact:
    """Milestone input for scheduler health evaluation."""

    title: str
    due_date: date
    status: MilestoneStatus


@dataclass(frozen=True, slots=True)
class HealthTimesheetFact:
    """Last-week hours input for scheduler health evaluation."""

    employee_full_name: str
    hours_logged: int
    expected_hours: int


@dataclass(frozen=True, slots=True)
class HealthEvaluationInput:
    """Facts gathered for a single project health evaluation."""

    as_of: date
    milestones: tuple[HealthMilestoneFact, ...]
    last_week_timesheets: tuple[HealthTimesheetFact, ...]
    has_active_allocations: bool


@dataclass(frozen=True, slots=True)
class HealthEvaluationResult:
    """Computed project health status and risk flags."""

    status: ProjectHealthStatus
    risk_flags: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class SchedulerRunResult:
    """Outcome counters for one scheduler tick."""

    employees_synced: int
    projects_evaluated: int
    missed_weeks_created: int
