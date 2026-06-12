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
    get_team_builder_service,
    get_team_timesheet_service,
    require_manager,
)
from prm.api.schemas.admin_allocations import AllocationSummaryResponse
from prm.api.schemas.manager import (
    ActiveEngineerResponse,
    BenchEngineerResponse,
    CreateAllocationRequest,
    EndAllocationRequest,
    EngineerAllocationDetailResponse,
    EngineerResourceDetailResponse,
    EngineerTimesheetEntryResponse,
    EngineerTimesheetWeekDetailResponse,
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
    TeamAvailabilityHintResponse,
    TeamMatchRequest,
    TeamMatchResponse,
    TeamRoleAssignmentResponse,
    TeamRoleGapResponse,
    TeamTimesheetListResponse,
    TeamTimesheetRowResponse,
)
from prm.application.allocation_service import AllocationService
from prm.application.manager_project_service import ManagerProjectService
from prm.application.resource_dashboard_service import ResourceDashboardService
from prm.application.risk_summary_service import RiskSummaryService
from prm.application.skill_match_service import SkillMatchService
from prm.application.team_builder_service import TeamBuilderService
from prm.application.team_timesheet_service import TeamTimesheetService
from prm.domain.dtos import (
    AllocationSummary,
    EngineerResourceDetail,
    EngineerTimesheetWeekDetail,
    ManagerProjectDetail,
    ManagerProjectListResult,
    ResourceDashboardResult,
    RiskSummaryResult,
    SkillMatchListResult,
    TeamBuilderResult,
    TeamRoleRequirement,
    TeamRoleSkillRequirement,
    TeamTimesheetListResult,
)
from prm.domain.entities.allocation import Allocation
from prm.infrastructure.security.jwt import JwtTokenPayload

router = APIRouter(prefix="/manager", tags=["manager"])


def _to_dashboard_response(result: ResourceDashboardResult) -> ResourceDashboardResponse:
    return ResourceDashboardResponse(
        on_bench=[
            BenchEngineerResponse(
                user_id=row.user_id,
                full_name=row.full_name,
                department=row.department,
                skill_names=list(row.skill_names),
            )
            for row in result.on_bench
        ],
        active=[
            ActiveEngineerResponse(
                user_id=row.user_id,
                full_name=row.full_name,
                utilisation_percent=row.utilisation_percent,
                availability_percent=row.availability_percent,
            )
            for row in result.active
        ],
        bench_count=result.bench_count,
        partial_count=result.partial_count,
    )


def _to_engineer_detail_response(detail: EngineerResourceDetail) -> EngineerResourceDetailResponse:
    return EngineerResourceDetailResponse(
        user_id=detail.user_id,
        full_name=detail.full_name,
        department=detail.department,
        work_status=detail.work_status,
        current_utilisation_percent=detail.current_utilisation_percent,
        profile_skills=list(detail.profile_skills),
        active_allocations=[
            EngineerAllocationDetailResponse(
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
        user_id=allocation.user_id,
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
                user_id=summary.user_id,
                user_full_name=summary.user_full_name,
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
                user_id=resource.user_id,
                user_full_name=resource.user_full_name,
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
                user_id=row.user_id,
                user_full_name=row.user_full_name,
                project_id=row.project_id,
                project_name=row.project_name,
                hours=row.hours,
                status=row.status,
            )
            for row in result.rows
        ],
        total=result.total,
    )


def _to_engineer_timesheet_week_detail_response(
    detail: EngineerTimesheetWeekDetail,
) -> EngineerTimesheetWeekDetailResponse:
    return EngineerTimesheetWeekDetailResponse(
        user_id=detail.user_id,
        user_full_name=detail.user_full_name,
        week_start_date=detail.week_start_date,
        status=detail.status,
        total_hours=detail.total_hours,
        entries=[
            EngineerTimesheetEntryResponse(
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
                user_id=match.user_id,
                user_name=match.user_name,
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


def _to_team_role_requirements(body: TeamMatchRequest) -> tuple[TeamRoleRequirement, ...]:
    return tuple(
        TeamRoleRequirement(
            role_label=role.role_label.strip(),
            required_skills=tuple(
                TeamRoleSkillRequirement(
                    skill_name=skill.skill_name.strip(),
                    min_proficiency=skill.min_proficiency,
                )
                for skill in role.required_skills
            ),
            hours_per_week=role.hours_per_week,
        )
        for role in body.roles
    )


def _to_team_match_response(result: TeamBuilderResult) -> TeamMatchResponse:
    return TeamMatchResponse(
        project_id=result.project_id,
        assignments=[
            TeamRoleAssignmentResponse(
                role_label=assignment.role_label,
                user_id=assignment.user_id,
                user_name=assignment.user_name,
                suggested_allocation_percent=assignment.suggested_allocation_percent,
                reason=assignment.reason,
                free_hours_per_week=assignment.free_hours_per_week,
            )
            for assignment in result.assignments
        ],
        gaps=[
            TeamRoleGapResponse(
                role_label=gap.role_label,
                gap_type=gap.gap_type,
                detail=gap.detail,
                availability_hints=[
                    TeamAvailabilityHintResponse(
                        user_name=hint.user_name,
                        available_from=hint.available_from,
                    )
                    for hint in gap.availability_hints
                ],
            )
            for gap in result.gaps
        ],
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
    "/timesheets/{user_id}",
    response_model=EngineerTimesheetWeekDetailResponse,
)
def get_engineer_timesheet_detail(
    user_id: int,
    manager: Annotated[JwtTokenPayload, Depends(require_manager)],
    service: Annotated[TeamTimesheetService, Depends(get_team_timesheet_service)],
    week_start_date: Annotated[date | None, Query()] = None,
) -> EngineerTimesheetWeekDetailResponse:
    week = week_start_date or _default_week_start()
    detail = service.get_engineer_timesheet_detail(manager.user_id, user_id, week)
    return _to_engineer_timesheet_week_detail_response(detail)


@router.get("/resources", response_model=ResourceDashboardResponse)
def get_resource_dashboard(
    manager: Annotated[JwtTokenPayload, Depends(require_manager)],
    service: Annotated[ResourceDashboardService, Depends(get_resource_dashboard_service)],
) -> ResourceDashboardResponse:
    return _to_dashboard_response(service.get_dashboard(manager.user_id))


@router.get("/resources/{user_id}", response_model=EngineerResourceDetailResponse)
def get_engineer_resource_detail(
    user_id: int,
    manager: Annotated[JwtTokenPayload, Depends(require_manager)],
    service: Annotated[ResourceDashboardService, Depends(get_resource_dashboard_service)],
) -> EngineerResourceDetailResponse:
    return _to_engineer_detail_response(
        service.get_engineer_detail(manager.user_id, user_id)
    )


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
        user_id=body.user_id,
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


@router.post("/projects/{project_id}/team-match", response_model=TeamMatchResponse)
def team_match(
    project_id: int,
    body: TeamMatchRequest,
    manager: Annotated[JwtTokenPayload, Depends(require_manager)],
    service: Annotated[TeamBuilderService, Depends(get_team_builder_service)],
) -> TeamMatchResponse:
    roles = _to_team_role_requirements(body)
    result = service.build_team(manager.user_id, project_id, roles)
    return _to_team_match_response(result)


@router.get("/projects/{project_id}/risk-summary", response_model=RiskSummaryResponse)
def get_risk_summary(
    project_id: int,
    manager: Annotated[JwtTokenPayload, Depends(require_manager)],
    service: Annotated[RiskSummaryService, Depends(get_risk_summary_service)],
) -> RiskSummaryResponse:
    result = service.summarize_risk(manager.user_id, project_id)
    return _to_risk_summary_response(result)
