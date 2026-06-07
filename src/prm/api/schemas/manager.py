"""Manager allocation and resource dashboard API schemas."""

from datetime import date

from pydantic import BaseModel, Field

from prm.api.schemas.admin_allocations import AllocationSummaryResponse
from prm.domain.enums import AllocationStatus, EmployeeWorkStatus


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
