"""Manager allocation, resource dashboard, projects, and timesheet API schemas."""

from datetime import date, datetime

from pydantic import BaseModel, Field

from prm.api.schemas.admin_allocations import AllocationSummaryResponse
from prm.domain.enums import (
    AllocationStatus,
    EmployeeWorkStatus,
    MilestoneStatus,
    ProjectHealthStatus,
    TimesheetWeekStatus,
)


class BenchEmployeeResponse(BaseModel):
    employee_id: int
    full_name: str
    department: str
    skill_names: list[str]


class ActiveEmployeeResponse(BaseModel):
    employee_id: int
    full_name: str
    utilisation_percent: int
    availability_percent: int


class ResourceDashboardResponse(BaseModel):
    on_bench: list[BenchEmployeeResponse]
    active: list[ActiveEmployeeResponse]
    bench_count: int
    over_utilised_count: int
    partial_count: int


class EmployeeAllocationDetailResponse(BaseModel):
    project_name: str
    utilisation_percent: int
    from_date: date
    to_date: date | None


class EmployeeResourceDetailResponse(BaseModel):
    employee_id: int
    full_name: str
    department: str
    work_status: EmployeeWorkStatus
    current_utilisation_percent: int
    profile_skills: list[str]
    active_allocations: list[EmployeeAllocationDetailResponse]
    recent_activity_tags: list[str]


class CreateAllocationRequest(BaseModel):
    project_id: int
    employee_id: int
    utilisation_percent: int = Field(ge=1, le=100)
    from_date: date
    to_date: date | None = None


class EndAllocationRequest(BaseModel):
    as_of: date | None = None


class ManagerAllocationResponse(BaseModel):
    allocation_id: int
    employee_id: int
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
    employee_id: int
    employee_full_name: str
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
    employee_id: int
    employee_full_name: str
    project_id: int
    project_name: str
    hours: int
    status: TimesheetWeekStatus


class TeamTimesheetListResponse(BaseModel):
    week_start_date: date
    rows: list[TeamTimesheetRowResponse]
    total: int


class EmployeeTimesheetEntryResponse(BaseModel):
    project_id: int
    project_name: str
    hours_worked: int
    activity_tags: list[str]


class EmployeeTimesheetWeekDetailResponse(BaseModel):
    employee_id: int
    employee_full_name: str
    week_start_date: date
    status: TimesheetWeekStatus
    total_hours: int
    entries: list[EmployeeTimesheetEntryResponse]


class SkillMatchRequest(BaseModel):
    requirement: str = Field(min_length=1)


class SkillMatchResultResponse(BaseModel):
    employee_id: int
    employee_name: str
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
