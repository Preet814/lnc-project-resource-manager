"""Admin allocation-view API response schemas."""

from datetime import date

from pydantic import BaseModel


class AllocationSummaryResponse(BaseModel):
    allocation_id: int
    employee_id: int
    employee_full_name: str
    project_id: int
    project_name: str
    utilisation_percent: int
    from_date: date
    to_date: date | None


class AllocationListResponse(BaseModel):
    allocations: list[AllocationSummaryResponse]
    total: int
