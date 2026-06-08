"""Employee timesheet and allocation endpoints (BRD Screen 5)."""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from prm.api.deps import (
    get_employee_allocation_service,
    get_employee_timesheet_service,
    require_employee,
)
from prm.api.schemas.employee import (
    MyAllocationRowResponse,
    MyAllocationsResponse,
    MyTimesheetEntryResponse,
    MyTimesheetListResponse,
    MyTimesheetWeekDetailResponse,
    MyTimesheetWeekSummaryResponse,
    SubmitTimesheetRequest,
    SubmittedTimesheetResponse,
    WeekAllocationRowResponse,
    WeekAllocationsResponse,
)
from prm.application.employee_allocation_service import EmployeeAllocationService
from prm.application.employee_timesheet_service import EmployeeTimesheetService
from prm.domain.dtos import (
    MyAllocationsResult,
    MyTimesheetListResult,
    MyTimesheetWeekDetail,
    SubmitTimesheetCommand,
    SubmitTimesheetEntry,
    SubmittedTimesheetResult,
    WeekAllocationsResult,
)
from prm.domain.week_calendar import week_start_on_or_before
from prm.infrastructure.security.jwt import JwtTokenPayload

router = APIRouter(prefix="/employee", tags=["employee"])


def _default_week_start() -> date:
    return week_start_on_or_before(date.today())


def _to_submitted_response(result: SubmittedTimesheetResult) -> SubmittedTimesheetResponse:
    return SubmittedTimesheetResponse(
        week_start_date=result.week_start_date,
        status=result.status,
        total_hours=result.total_hours,
        submitted_at=result.submitted_at,
    )


def _to_week_allocations_response(result: WeekAllocationsResult) -> WeekAllocationsResponse:
    return WeekAllocationsResponse(
        week_start_date=result.week_start_date,
        max_weekly_hours=result.max_weekly_hours,
        allocations=[
            WeekAllocationRowResponse(
                project_id=row.project_id,
                project_name=row.project_name,
                utilisation_percent=row.utilisation_percent,
                expected_max_hours=row.expected_max_hours,
            )
            for row in result.allocations
        ],
    )


def _to_my_allocations_response(result: MyAllocationsResult) -> MyAllocationsResponse:
    return MyAllocationsResponse(
        allocations=[
            MyAllocationRowResponse(
                project_id=row.project_id,
                project_name=row.project_name,
                utilisation_percent=row.utilisation_percent,
                from_date=row.from_date,
                to_date=row.to_date,
                status=row.status,
            )
            for row in result.allocations
        ],
        total_utilisation_percent=result.total_utilisation_percent,
    )


def _to_my_timesheet_list_response(result: MyTimesheetListResult) -> MyTimesheetListResponse:
    return MyTimesheetListResponse(
        weeks=[
            MyTimesheetWeekSummaryResponse(
                week_start_date=week.week_start_date,
                total_hours=week.total_hours,
                status=week.status,
            )
            for week in result.weeks
        ],
        total=result.total,
    )


def _to_my_timesheet_detail_response(
    detail: MyTimesheetWeekDetail,
) -> MyTimesheetWeekDetailResponse:
    return MyTimesheetWeekDetailResponse(
        week_start_date=detail.week_start_date,
        status=detail.status,
        total_hours=detail.total_hours,
        entries=[
            MyTimesheetEntryResponse(
                project_id=entry.project_id,
                project_name=entry.project_name,
                hours_worked=entry.hours_worked,
                activity_tags=list(entry.activity_tags),
            )
            for entry in detail.entries
        ],
    )


@router.get("/allocations/for-week", response_model=WeekAllocationsResponse)
def list_allocations_for_week(
    employee: Annotated[JwtTokenPayload, Depends(require_employee)],
    service: Annotated[EmployeeAllocationService, Depends(get_employee_allocation_service)],
    week_start_date: Annotated[date | None, Query()] = None,
) -> WeekAllocationsResponse:
    week = week_start_date or _default_week_start()
    result = service.list_allocations_for_week(employee.user_id, week)
    return _to_week_allocations_response(result)


@router.get("/allocations", response_model=MyAllocationsResponse)
def list_my_allocations(
    employee: Annotated[JwtTokenPayload, Depends(require_employee)],
    service: Annotated[EmployeeAllocationService, Depends(get_employee_allocation_service)],
) -> MyAllocationsResponse:
    result = service.list_my_allocations(employee.user_id)
    return _to_my_allocations_response(result)


@router.post(
    "/timesheets",
    response_model=SubmittedTimesheetResponse,
    status_code=status.HTTP_201_CREATED,
)
def submit_timesheet(
    body: SubmitTimesheetRequest,
    employee: Annotated[JwtTokenPayload, Depends(require_employee)],
    service: Annotated[EmployeeTimesheetService, Depends(get_employee_timesheet_service)],
) -> SubmittedTimesheetResponse:
    command = SubmitTimesheetCommand(
        week_start_date=body.week_start_date,
        entries=tuple(
            SubmitTimesheetEntry(
                project_id=entry.project_id,
                hours_worked=entry.hours_worked,
                activity_tags=tuple(entry.activity_tags),
            )
            for entry in body.entries
        ),
    )
    result = service.submit_week(employee.user_id, command)
    return _to_submitted_response(result)


@router.get("/timesheets", response_model=MyTimesheetListResponse)
def list_my_timesheets(
    employee: Annotated[JwtTokenPayload, Depends(require_employee)],
    service: Annotated[EmployeeTimesheetService, Depends(get_employee_timesheet_service)],
) -> MyTimesheetListResponse:
    result = service.list_my_timesheets(employee.user_id)
    return _to_my_timesheet_list_response(result)


@router.get("/timesheets/{week_start_date}", response_model=MyTimesheetWeekDetailResponse)
def get_my_timesheet_detail(
    week_start_date: date,
    employee: Annotated[JwtTokenPayload, Depends(require_employee)],
    service: Annotated[EmployeeTimesheetService, Depends(get_employee_timesheet_service)],
) -> MyTimesheetWeekDetailResponse:
    detail = service.get_my_timesheet_detail(employee.user_id, week_start_date)
    return _to_my_timesheet_detail_response(detail)
