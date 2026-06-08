"""Employee timesheet and allocation API schemas."""

from datetime import date, datetime

from pydantic import BaseModel, Field

from prm.domain.enums import ActivityTag, AllocationStatus, TimesheetWeekStatus


class SubmitTimesheetEntryRequest(BaseModel):
    project_id: int
    hours_worked: int = Field(ge=0)
    activity_tags: list[ActivityTag] = Field(default_factory=list)


class SubmitTimesheetRequest(BaseModel):
    week_start_date: date
    entries: list[SubmitTimesheetEntryRequest]


class SubmittedTimesheetResponse(BaseModel):
    week_start_date: date
    status: TimesheetWeekStatus
    total_hours: int
    submitted_at: datetime


class WeekAllocationRowResponse(BaseModel):
    project_id: int
    project_name: str
    utilisation_percent: int
    expected_max_hours: int


class WeekAllocationsResponse(BaseModel):
    week_start_date: date
    max_weekly_hours: int
    allocations: list[WeekAllocationRowResponse]


class MyAllocationRowResponse(BaseModel):
    project_id: int
    project_name: str
    utilisation_percent: int
    from_date: date
    to_date: date | None
    status: AllocationStatus


class MyAllocationsResponse(BaseModel):
    allocations: list[MyAllocationRowResponse]
    total_utilisation_percent: int


class MyTimesheetWeekSummaryResponse(BaseModel):
    week_start_date: date
    total_hours: int
    status: TimesheetWeekStatus


class MyTimesheetListResponse(BaseModel):
    weeks: list[MyTimesheetWeekSummaryResponse]
    total: int


class MyTimesheetEntryResponse(BaseModel):
    project_id: int
    project_name: str
    hours_worked: int
    activity_tags: list[str]


class MyTimesheetWeekDetailResponse(BaseModel):
    week_start_date: date
    status: TimesheetWeekStatus
    total_hours: int
    entries: list[MyTimesheetEntryResponse]
