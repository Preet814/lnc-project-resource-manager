"""Manager resource dashboard, allocation, projects, and timesheet endpoints."""

from datetime import date, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from prm.api.deps import (
    get_allocation_service,
    get_db_session,
    get_manager_project_service,
    get_resource_dashboard_service,
    get_risk_summary_service,
    get_skill_match_service,
    get_team_timesheet_service,
    require_manager,
)
from prm.api.schemas.admin_allocations import AllocationSummaryResponse
from prm.api.schemas.manager import (
    ActiveEmployeeResponse,
    BenchEmployeeResponse,
    CreateAllocationRequest,
    EmployeeAllocationDetailResponse,
    EmployeeResourceDetailResponse,
    EmployeeTimesheetEntryResponse,
    EmployeeTimesheetWeekDetailResponse,
    EndAllocationRequest,
    ManagerAllocationResponse,
    ManagerProjectDetailResponse,
    ManagerProjectListResponse,
    ManagerProjectMilestoneResponse,
    ManagerProjectResourceResponse,
    ManagerProjectSummaryResponse,
    ProjectAllocationListResponse,
    ResourceDashboardResponse,
    RiskSummaryResponse,
    SkillMatchRequest,
    SkillMatchResponse,
    SkillMatchResultResponse,
    TeamTimesheetListResponse,
    TeamTimesheetRowResponse,
)
from prm.application.allocation_service import AllocationService
from prm.application.manager_project_service import ManagerProjectService
from prm.application.resource_dashboard_service import ResourceDashboardService
from prm.application.risk_summary_service import RiskSummaryService
from prm.application.skill_match_service import SkillMatchService
from prm.application.team_timesheet_service import TeamTimesheetService
from prm.domain.dtos import (
    AllocationSummary,
    EmployeeResourceDetail,
    EmployeeTimesheetWeekDetail,
    ManagerProjectDetail,
    ManagerProjectListResult,
    ResourceDashboardResult,
    RiskSummaryResult,
    SkillMatchListResult,
    TeamTimesheetListResult,
)
from prm.domain.entities.allocation import Allocation
from prm.infrastructure.security.jwt import JwtTokenPayload

router = APIRouter(prefix="/manager", tags=["manager"])


def _to_dashboard_response(result: ResourceDashboardResult) -> ResourceDashboardResponse:
    return ResourceDashboardResponse(
        on_bench=[
            BenchEmployeeResponse(
                employee_id=row.employee_id,
                full_name=row.full_name,
                department=row.department,
                skill_names=list(row.skill_names),
            )
            for row in result.on_bench
        ],
        active=[
            ActiveEmployeeResponse(
                employee_id=row.employee_id,
                full_name=row.full_name,
                utilisation_percent=row.utilisation_percent,
                availability_percent=row.availability_percent,
            )
            for row in result.active
        ],
        bench_count=result.bench_count,
        over_utilised_count=result.over_utilised_count,
        partial_count=result.partial_count,
    )


def _to_employee_detail_response(detail: EmployeeResourceDetail) -> EmployeeResourceDetailResponse:
    return EmployeeResourceDetailResponse(
        employee_id=detail.employee_id,
        full_name=detail.full_name,
        department=detail.department,
        work_status=detail.work_status,
        current_utilisation_percent=detail.current_utilisation_percent,
        profile_skills=list(detail.profile_skills),
        active_allocations=[
            EmployeeAllocationDetailResponse(
                project_name=allocation.project_name,
                utilisation_percent=allocation.utilisation_percent,
                from_date=allocation.from_date,
                to_date=allocation.to_date,
            )
            for allocation in detail.active_allocations
        ],
        recent_activity_tags=list(detail.recent_activity_tags),
    )


def _to_allocation_response(allocation: Allocation) -> ManagerAllocationResponse:
    return ManagerAllocationResponse(
        allocation_id=allocation.id,
        employee_id=allocation.employee_id,
        project_id=allocation.project_id,
        utilisation_percent=allocation.utilisation_percent,
        from_date=allocation.from_date,
        to_date=allocation.to_date,
        status=allocation.status,
    )


def _to_project_allocation_list_response(
    allocations: tuple[AllocationSummary, ...],
) -> ProjectAllocationListResponse:
    return ProjectAllocationListResponse(
        allocations=[
            AllocationSummaryResponse(
                allocation_id=summary.allocation_id,
                employee_id=summary.employee_id,
                employee_full_name=summary.employee_full_name,
                project_id=summary.project_id,
                project_name=summary.project_name,
                utilisation_percent=summary.utilisation_percent,
                from_date=summary.from_date,
                to_date=summary.to_date,
            )
            for summary in allocations
        ],
        total=len(allocations),
    )


def _default_week_start() -> date:
    today = date.today()
    return today - timedelta(days=today.weekday())


def _to_manager_project_list_response(
    result: ManagerProjectListResult,
) -> ManagerProjectListResponse:
    return ManagerProjectListResponse(
        projects=[
            ManagerProjectSummaryResponse(
                project_id=project.project_id,
                name=project.name,
                end_date=project.end_date,
                health_status=project.health_status,
            )
            for project in result.projects
        ],
        total=result.total,
    )


def _to_manager_project_detail_response(
    detail: ManagerProjectDetail,
) -> ManagerProjectDetailResponse:
    return ManagerProjectDetailResponse(
        project_id=detail.project_id,
        name=detail.name,
        health_status=detail.health_status,
        health_computed_at=detail.health_computed_at,
        risk_flags=list(detail.risk_flags),
        milestones=[
            ManagerProjectMilestoneResponse(
                milestone_id=milestone.milestone_id,
                title=milestone.title,
                due_date=milestone.due_date,
                status=milestone.status,
                sequence_order=milestone.sequence_order,
                is_overdue=milestone.is_overdue,
            )
            for milestone in detail.milestones
        ],
        allocated_resources=[
            ManagerProjectResourceResponse(
                employee_id=resource.employee_id,
                employee_full_name=resource.employee_full_name,
                utilisation_percent=resource.utilisation_percent,
                from_date=resource.from_date,
                to_date=resource.to_date,
            )
            for resource in detail.allocated_resources
        ],
    )


def _to_team_timesheet_list_response(
    result: TeamTimesheetListResult,
) -> TeamTimesheetListResponse:
    return TeamTimesheetListResponse(
        week_start_date=result.week_start_date,
        rows=[
            TeamTimesheetRowResponse(
                employee_id=row.employee_id,
                employee_full_name=row.employee_full_name,
                project_id=row.project_id,
                project_name=row.project_name,
                hours=row.hours,
                status=row.status,
            )
            for row in result.rows
        ],
        total=result.total,
    )


def _to_employee_timesheet_week_detail_response(
    detail: EmployeeTimesheetWeekDetail,
) -> EmployeeTimesheetWeekDetailResponse:
    return EmployeeTimesheetWeekDetailResponse(
        employee_id=detail.employee_id,
        employee_full_name=detail.employee_full_name,
        week_start_date=detail.week_start_date,
        status=detail.status,
        total_hours=detail.total_hours,
        entries=[
            EmployeeTimesheetEntryResponse(
                project_id=entry.project_id,
                project_name=entry.project_name,
                hours_worked=entry.hours_worked,
                activity_tags=list(entry.activity_tags),
            )
            for entry in detail.entries
        ],
    )


def _to_skill_match_response(result: SkillMatchListResult) -> SkillMatchResponse:
    return SkillMatchResponse(
        project_id=result.project_id,
        requirement=result.requirement,
        matches=[
            SkillMatchResultResponse(
                employee_id=match.employee_id,
                employee_name=match.employee_name,
                reason=match.reason,
                suggested_allocation_percent=match.suggested_allocation_percent,
                free_hours_per_week=match.free_hours_per_week,
            )
            for match in result.matches
        ],
        total=result.total,
        message=result.message,
    )


def _to_risk_summary_response(result: RiskSummaryResult) -> RiskSummaryResponse:
    return RiskSummaryResponse(
        project_id=result.project_id,
        summary=result.summary,
        disclaimer=result.disclaimer,
    )


@router.get("/projects", response_model=ManagerProjectListResponse)
def list_my_projects(
    manager: Annotated[JwtTokenPayload, Depends(require_manager)],
    service: Annotated[ManagerProjectService, Depends(get_manager_project_service)],
) -> ManagerProjectListResponse:
    return _to_manager_project_list_response(service.list_my_projects(manager.user_id))


@router.get("/projects/{project_id}", response_model=ManagerProjectDetailResponse)
def get_project_detail(
    project_id: int,
    manager: Annotated[JwtTokenPayload, Depends(require_manager)],
    service: Annotated[ManagerProjectService, Depends(get_manager_project_service)],
) -> ManagerProjectDetailResponse:
    detail = service.get_project_detail(manager.user_id, project_id)
    return _to_manager_project_detail_response(detail)


@router.get("/timesheets", response_model=TeamTimesheetListResponse)
def list_team_timesheets(
    manager: Annotated[JwtTokenPayload, Depends(require_manager)],
    service: Annotated[TeamTimesheetService, Depends(get_team_timesheet_service)],
    week_start_date: Annotated[date | None, Query()] = None,
) -> TeamTimesheetListResponse:
    week = week_start_date or _default_week_start()
    result = service.list_team_timesheets(manager.user_id, week)
    return _to_team_timesheet_list_response(result)


@router.get(
    "/timesheets/{employee_id}",
    response_model=EmployeeTimesheetWeekDetailResponse,
)
def get_employee_timesheet_detail(
    employee_id: int,
    manager: Annotated[JwtTokenPayload, Depends(require_manager)],
    service: Annotated[TeamTimesheetService, Depends(get_team_timesheet_service)],
    week_start_date: Annotated[date | None, Query()] = None,
) -> EmployeeTimesheetWeekDetailResponse:
    week = week_start_date or _default_week_start()
    detail = service.get_employee_timesheet_detail(manager.user_id, employee_id, week)
    return _to_employee_timesheet_week_detail_response(detail)


@router.get("/resources", response_model=ResourceDashboardResponse)
def get_resource_dashboard(
    _manager: Annotated[JwtTokenPayload, Depends(require_manager)],
    service: Annotated[ResourceDashboardService, Depends(get_resource_dashboard_service)],
) -> ResourceDashboardResponse:
    return _to_dashboard_response(service.get_dashboard())


@router.get("/resources/{employee_id}", response_model=EmployeeResourceDetailResponse)
def get_employee_resource_detail(
    employee_id: int,
    _manager: Annotated[JwtTokenPayload, Depends(require_manager)],
    service: Annotated[ResourceDashboardService, Depends(get_resource_dashboard_service)],
) -> EmployeeResourceDetailResponse:
    return _to_employee_detail_response(service.get_employee_detail(employee_id))


@router.get(
    "/projects/{project_id}/allocations",
    response_model=ProjectAllocationListResponse,
)
def list_project_allocations(
    project_id: int,
    manager: Annotated[JwtTokenPayload, Depends(require_manager)],
    service: Annotated[AllocationService, Depends(get_allocation_service)],
) -> ProjectAllocationListResponse:
    allocations = service.list_project_allocations(manager.user_id, project_id)
    return _to_project_allocation_list_response(allocations)


@router.post(
    "/allocations",
    response_model=ManagerAllocationResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_allocation(
    body: CreateAllocationRequest,
    manager: Annotated[JwtTokenPayload, Depends(require_manager)],
    service: Annotated[AllocationService, Depends(get_allocation_service)],
    db: Annotated[Session, Depends(get_db_session)],
) -> ManagerAllocationResponse:
    allocation = service.allocate_direct(
        manager.user_id,
        project_id=body.project_id,
        employee_id=body.employee_id,
        utilisation_percent=body.utilisation_percent,
        from_date=body.from_date,
        to_date=body.to_date,
    )
    db.commit()
    return _to_allocation_response(allocation)


@router.post(
    "/allocations/{allocation_id}/end",
    response_model=ManagerAllocationResponse,
)
def end_allocation(
    allocation_id: int,
    body: EndAllocationRequest,
    manager: Annotated[JwtTokenPayload, Depends(require_manager)],
    service: Annotated[AllocationService, Depends(get_allocation_service)],
    db: Annotated[Session, Depends(get_db_session)],
) -> ManagerAllocationResponse:
    allocation = service.end_allocation(
        manager.user_id,
        allocation_id,
        as_of=body.as_of,
    )
    db.commit()
    return _to_allocation_response(allocation)


@router.post("/projects/{project_id}/skill-match", response_model=SkillMatchResponse)
def skill_match(
    project_id: int,
    body: SkillMatchRequest,
    manager: Annotated[JwtTokenPayload, Depends(require_manager)],
    service: Annotated[SkillMatchService, Depends(get_skill_match_service)],
) -> SkillMatchResponse:
    result = service.find_matches(manager.user_id, project_id, body.requirement)
    return _to_skill_match_response(result)


@router.get("/projects/{project_id}/risk-summary", response_model=RiskSummaryResponse)
def get_risk_summary(
    project_id: int,
    manager: Annotated[JwtTokenPayload, Depends(require_manager)],
    service: Annotated[RiskSummaryService, Depends(get_risk_summary_service)],
) -> RiskSummaryResponse:
    result = service.summarize_risk(manager.user_id, project_id)
    return _to_risk_summary_response(result)
