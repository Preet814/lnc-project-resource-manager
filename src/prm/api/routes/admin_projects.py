"""Admin project-management endpoints (BRD §3.2)."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from prm.api.deps import (
    get_db_session,
    get_project_management_service,
    get_project_milestone_service,
    require_admin,
)
from prm.api.schemas.admin_projects import (
    AddMilestoneRequest,
    CreateProjectRequest,
    MilestoneListResponse,
    MilestoneResponse,
    ProjectListResponse,
    ProjectResponse,
    ProjectSummaryResponse,
    UpdateMilestoneRequest,
    UpdateProjectRequest,
)
from prm.application.project_management_service import ProjectManagementService
from prm.application.project_milestone_service import ProjectMilestoneService
from prm.domain.dtos import MilestoneDetail, MilestoneListResult, ProjectListResult
from prm.domain.entities.project import Project
from prm.domain.enums import ProjectStatus
from prm.infrastructure.security.jwt import JwtTokenPayload

router = APIRouter(prefix="/admin/projects", tags=["admin-projects"])


def _to_project_response(project: Project) -> ProjectResponse:
    return ProjectResponse(
        id=project.id,
        name=project.name,
        description=project.description,
        start_date=project.start_date,
        end_date=project.end_date,
        status=project.status,
        manager_user_id=project.manager_user_id,
        total_story_points=project.total_story_points,
        health_status=project.health_status,
        health_computed_at=project.health_computed_at,
    )


def _to_project_list_response(result: ProjectListResult) -> ProjectListResponse:
    return ProjectListResponse(
        projects=[
            ProjectSummaryResponse(
                id=summary.id,
                name=summary.name,
                manager_full_name=summary.manager_full_name,
                end_date=summary.end_date,
                status=summary.status,
                story_points_done=summary.story_points_done,
                story_points_total=summary.story_points_total,
            )
            for summary in result.projects
        ],
        total=result.total,
        active_count=result.active_count,
        planned_count=result.planned_count,
        on_hold_count=result.on_hold_count,
        completed_count=result.completed_count,
    )


def _to_milestone_response(detail: MilestoneDetail) -> MilestoneResponse:
    return MilestoneResponse(
        milestone_id=detail.milestone_id,
        title=detail.title,
        due_date=detail.due_date,
        status=detail.status,
        sequence_order=detail.sequence_order,
        story_points=detail.story_points,
    )


def _to_milestone_list_response(result: MilestoneListResult) -> MilestoneListResponse:
    return MilestoneListResponse(
        milestones=[_to_milestone_response(milestone) for milestone in result.milestones],
        total_story_points=result.total_story_points,
        completed_story_points=result.completed_story_points,
        remaining_story_points=result.remaining_story_points,
    )


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
def create_project(
    body: CreateProjectRequest,
    _admin: Annotated[JwtTokenPayload, Depends(require_admin)],
    service: Annotated[ProjectManagementService, Depends(get_project_management_service)],
    db: Annotated[Session, Depends(get_db_session)],
) -> ProjectResponse:
    created = service.create_project(
        name=body.name,
        description=body.description,
        start_date=body.start_date,
        end_date=body.end_date,
        status=body.status,
        manager_user_id=body.manager_user_id,
        total_story_points=body.total_story_points,
    )
    db.commit()
    return _to_project_response(created)


@router.get("", response_model=ProjectListResponse)
def list_projects(
    _admin: Annotated[JwtTokenPayload, Depends(require_admin)],
    service: Annotated[ProjectManagementService, Depends(get_project_management_service)],
    project_status: Annotated[ProjectStatus | None, Query(alias="status")] = None,
) -> ProjectListResponse:
    return _to_project_list_response(
        service.list_projects(status=project_status),
    )


@router.get("/{project_id}", response_model=ProjectResponse)
def get_project(
    project_id: int,
    _admin: Annotated[JwtTokenPayload, Depends(require_admin)],
    service: Annotated[ProjectManagementService, Depends(get_project_management_service)],
) -> ProjectResponse:
    return _to_project_response(service.get_project(project_id))


@router.patch("/{project_id}", response_model=ProjectResponse)
def update_project(
    project_id: int,
    body: UpdateProjectRequest,
    _admin: Annotated[JwtTokenPayload, Depends(require_admin)],
    service: Annotated[ProjectManagementService, Depends(get_project_management_service)],
    db: Annotated[Session, Depends(get_db_session)],
) -> ProjectResponse:
    updated = service.update_project(
        project_id,
        name=body.name,
        description=body.description,
        start_date=body.start_date,
        end_date=body.end_date,
        status=body.status,
        manager_user_id=body.manager_user_id,
        total_story_points=body.total_story_points,
    )
    db.commit()
    return _to_project_response(updated)


@router.get("/{project_id}/milestones", response_model=MilestoneListResponse)
def list_project_milestones(
    project_id: int,
    _admin: Annotated[JwtTokenPayload, Depends(require_admin)],
    service: Annotated[ProjectMilestoneService, Depends(get_project_milestone_service)],
) -> MilestoneListResponse:
    return _to_milestone_list_response(service.list_milestones(project_id))


@router.post(
    "/{project_id}/milestones",
    response_model=MilestoneResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_project_milestone(
    project_id: int,
    body: AddMilestoneRequest,
    _admin: Annotated[JwtTokenPayload, Depends(require_admin)],
    service: Annotated[ProjectMilestoneService, Depends(get_project_milestone_service)],
    db: Annotated[Session, Depends(get_db_session)],
) -> MilestoneResponse:
    added = service.add_milestone(
        project_id,
        title=body.title,
        due_date=body.due_date,
        status=body.status,
        sequence_order=body.sequence_order,
        story_points=body.story_points,
    )
    db.commit()
    return _to_milestone_response(added)


@router.patch("/{project_id}/milestones/{milestone_id}", response_model=MilestoneResponse)
def update_project_milestone(
    project_id: int,
    milestone_id: int,
    body: UpdateMilestoneRequest,
    _admin: Annotated[JwtTokenPayload, Depends(require_admin)],
    service: Annotated[ProjectMilestoneService, Depends(get_project_milestone_service)],
    db: Annotated[Session, Depends(get_db_session)],
) -> MilestoneResponse:
    updated = service.update_milestone(
        project_id,
        milestone_id,
        title=body.title,
        due_date=body.due_date,
        status=body.status,
        sequence_order=body.sequence_order,
        story_points=body.story_points,
    )
    db.commit()
    return _to_milestone_response(updated)
