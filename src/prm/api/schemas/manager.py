"""Manager allocation, resource dashboard, projects, and timesheet API schemas."""

from datetime import date, datetime

from pydantic import BaseModel, Field

from prm.api.schemas.admin_allocations import AllocationSummaryResponse
from prm.domain.enums import (
    AllocationStatus,
    MilestoneStatus,
    ProjectHealthStatus,
    ResourceWorkStatus,
    TimesheetWeekStatus,
)


class BenchEngineerResponse(BaseModel):
    user_id: int
    full_name: str
    department: str
    skill_names: list[str]


class ActiveEngineerResponse(BaseModel):
    user_id: int
    full_name: str
    utilisation_percent: int
    availability_percent: int


class ResourceDashboardResponse(BaseModel):
    on_bench: list[BenchEngineerResponse]
    active: list[ActiveEngineerResponse]
    bench_count: int
    partial_count: int


class EngineerAllocationDetailResponse(BaseModel):
    project_name: str
    utilisation_percent: int
    from_date: date
    to_date: date | None


class EngineerResourceDetailResponse(BaseModel):
    user_id: int
    full_name: str
    department: str
    work_status: ResourceWorkStatus
    current_utilisation_percent: int
    profile_skills: list[str]
    active_allocations: list[EngineerAllocationDetailResponse]
    recent_activity_tags: list[str]


class CreateAllocationRequest(BaseModel):
    project_id: int
    user_id: int
    utilisation_percent: int = Field(ge=1, le=100)
    from_date: date
    to_date: date | None = None


class EndAllocationRequest(BaseModel):
    as_of: date | None = None


class ManagerAllocationResponse(BaseModel):
    allocation_id: int
    user_id: int
    project_id: int
    utilisation_percent: int
    from_date: date
    to_date: date | None
    status: AllocationStatus


class ProjectAllocationListResponse(BaseModel):
    allocations: list[AllocationSummaryResponse]
    total: int


class ManagerProjectSummaryResponse(BaseModel):
    project_id: int
    name: str
    end_date: date | None
    health_status: ProjectHealthStatus


class ManagerProjectListResponse(BaseModel):
    projects: list[ManagerProjectSummaryResponse]
    total: int


class ManagerProjectMilestoneResponse(BaseModel):
    milestone_id: int
    title: str
    due_date: date
    status: MilestoneStatus
    sequence_order: int
    is_overdue: bool


class ManagerProjectResourceResponse(BaseModel):
    user_id: int
    user_full_name: str
    utilisation_percent: int
    from_date: date
    to_date: date | None


class ManagerProjectDetailResponse(BaseModel):
    project_id: int
    name: str
    health_status: ProjectHealthStatus
    health_computed_at: datetime | None
    risk_flags: list[str]
    milestones: list[ManagerProjectMilestoneResponse]
    allocated_resources: list[ManagerProjectResourceResponse]


class TeamTimesheetRowResponse(BaseModel):
    user_id: int
    user_full_name: str
    project_id: int
    project_name: str
    hours: int
    status: TimesheetWeekStatus


class TeamTimesheetListResponse(BaseModel):
    week_start_date: date
    rows: list[TeamTimesheetRowResponse]
    total: int


class EngineerTimesheetEntryResponse(BaseModel):
    project_id: int
    project_name: str
    hours_worked: int
    activity_tags: list[str]


class EngineerTimesheetWeekDetailResponse(BaseModel):
    user_id: int
    user_full_name: str
    week_start_date: date
    status: TimesheetWeekStatus
    total_hours: int
    entries: list[EngineerTimesheetEntryResponse]


class SkillMatchRequest(BaseModel):
    requirement: str = Field(min_length=1)


class SkillMatchResultResponse(BaseModel):
    user_id: int
    user_name: str
    reason: str
    suggested_allocation_percent: int
    free_hours_per_week: int


class SkillMatchResponse(BaseModel):
    project_id: int
    requirement: str
    matches: list[SkillMatchResultResponse]
    total: int
    message: str | None = None


class RiskSummaryResponse(BaseModel):
    project_id: int
    summary: str
    disclaimer: str
