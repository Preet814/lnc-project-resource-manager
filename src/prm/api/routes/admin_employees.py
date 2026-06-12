"""Admin engineer-profile endpoints (BRD §3.1)."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from prm.api.deps import (
    get_db_session,
    get_user_profile_service,
    get_user_skill_service,
    require_permission,
)
from prm.api.schemas.admin_employees import (
    AddUserSkillRequest,
    AssignManagerRequest,
    CreateEmployeeRequest,
    EmployeeResponse,
    EngineerListResponse,
    EngineerSummaryResponse,
    UpdateEmployeeRequest,
    UpdateUserSkillRequest,
    UserSkillListResponse,
    UserSkillResponse,
)
from prm.application.user_profile_service import UserProfileService
from prm.application.user_skill_service import UserSkillService
from prm.domain.dtos import EngineerListResult, UserSkillDetail
from prm.domain.entities.user import User
from prm.domain.enums import ResourceWorkStatus
from prm.domain.permission_codes import (
    ENGINEER_ASSIGN_MANAGER,
    ENGINEER_MANAGE,
    SKILL_MANAGE_ANY,
)
from prm.infrastructure.security.jwt import JwtTokenPayload

router = APIRouter(prefix="/admin/employees", tags=["admin-employees"])


def _to_employee_response(user: User) -> EmployeeResponse:
    return EmployeeResponse(
        id=user.id,
        manager_id=user.manager_id,
        full_name=user.full_name,
        email=user.email,
        department=user.department_name or "",
        designation=user.designation_name or "",
        work_status=user.work_status or ResourceWorkStatus.BENCH,
        is_active=user.is_active(),
        current_utilisation_percent=user.utilisation_percent or 0,
        created_at=user.created_at,
    )


def _to_employee_list_response(result: EngineerListResult) -> EngineerListResponse:
    return EngineerListResponse(
        engineers=[
            EngineerSummaryResponse(
                id=summary.id,
                full_name=summary.full_name,
                department=summary.department,
                designation=summary.designation,
                work_status=summary.work_status,
                is_active=summary.is_active,
            )
            for summary in result.engineers
        ],
        total=result.total,
        allocated_count=result.allocated_count,
        bench_count=result.bench_count,
    )


def _to_skill_response(detail: UserSkillDetail) -> UserSkillResponse:
    return UserSkillResponse(
        user_skill_id=detail.user_skill_id,
        skill_id=detail.skill_id,
        skill_name=detail.skill_name,
        category=detail.category,
        proficiency=detail.proficiency,
        assigned_at=detail.assigned_at,
    )


def _to_skill_list_response(
    skills: tuple[UserSkillDetail, ...],
) -> UserSkillListResponse:
    return UserSkillListResponse(
        skills=[_to_skill_response(skill) for skill in skills],
    )


@router.post("", response_model=EmployeeResponse, status_code=status.HTTP_201_CREATED)
def create_employee(
    body: CreateEmployeeRequest,
    _admin: Annotated[JwtTokenPayload, Depends(require_permission(ENGINEER_MANAGE))],
    service: Annotated[UserProfileService, Depends(get_user_profile_service)],
    db: Annotated[Session, Depends(get_db_session)],
) -> EmployeeResponse:
    created = service.create_employee(
        user_id=body.user_id,
        full_name=body.full_name,
        email=body.email,
        department=body.department,
        designation=body.designation,
    )
    db.commit()
    return _to_employee_response(created)


@router.get("", response_model=EngineerListResponse)
def list_employees(
    _admin: Annotated[JwtTokenPayload, Depends(require_permission(ENGINEER_MANAGE))],
    service: Annotated[UserProfileService, Depends(get_user_profile_service)],
    work_status: ResourceWorkStatus | None = None,
    department: str | None = None,
    active_only: Annotated[bool, Query()] = True,
) -> EngineerListResponse:
    return _to_employee_list_response(
        service.list_employees(
            work_status=work_status,
            department=department,
            active_only=active_only,
        )
    )


@router.post("/assign-manager", response_model=EmployeeResponse)
def assign_manager(
    body: AssignManagerRequest,
    _admin: Annotated[
        JwtTokenPayload, Depends(require_permission(ENGINEER_ASSIGN_MANAGER))
    ],
    service: Annotated[UserProfileService, Depends(get_user_profile_service)],
    db: Annotated[Session, Depends(get_db_session)],
) -> EmployeeResponse:
    updated = service.assign_manager(
        engineer_user_id=body.engineer_user_id,
        manager_user_id=body.manager_user_id,
    )
    db.commit()
    return _to_employee_response(updated)


@router.get("/{user_id}", response_model=EmployeeResponse)
def get_employee(
    user_id: int,
    _admin: Annotated[JwtTokenPayload, Depends(require_permission(ENGINEER_MANAGE))],
    service: Annotated[UserProfileService, Depends(get_user_profile_service)],
) -> EmployeeResponse:
    return _to_employee_response(service.get_employee(user_id))


@router.patch("/{user_id}", response_model=EmployeeResponse)
def update_employee(
    user_id: int,
    body: UpdateEmployeeRequest,
    _admin: Annotated[JwtTokenPayload, Depends(require_permission(ENGINEER_MANAGE))],
    service: Annotated[UserProfileService, Depends(get_user_profile_service)],
    db: Annotated[Session, Depends(get_db_session)],
) -> EmployeeResponse:
    updated = service.update_employee(
        user_id,
        full_name=body.full_name,
        email=body.email,
        department=body.department,
        designation=body.designation,
    )
    db.commit()
    return _to_employee_response(updated)


@router.post("/{user_id}/deactivate", response_model=EmployeeResponse)
def deactivate_employee(
    user_id: int,
    _admin: Annotated[JwtTokenPayload, Depends(require_permission(ENGINEER_MANAGE))],
    service: Annotated[UserProfileService, Depends(get_user_profile_service)],
    db: Annotated[Session, Depends(get_db_session)],
) -> EmployeeResponse:
    deactivated = service.deactivate_employee(user_id)
    db.commit()
    return _to_employee_response(deactivated)


@router.get("/{user_id}/skills", response_model=UserSkillListResponse)
def list_user_skills(
    user_id: int,
    _admin: Annotated[JwtTokenPayload, Depends(require_permission(SKILL_MANAGE_ANY))],
    service: Annotated[UserSkillService, Depends(get_user_skill_service)],
) -> UserSkillListResponse:
    return _to_skill_list_response(service.list_skills(user_id))


@router.post(
    "/{user_id}/skills",
    response_model=UserSkillResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_user_skill(
    user_id: int,
    body: AddUserSkillRequest,
    _admin: Annotated[JwtTokenPayload, Depends(require_permission(SKILL_MANAGE_ANY))],
    service: Annotated[UserSkillService, Depends(get_user_skill_service)],
    db: Annotated[Session, Depends(get_db_session)],
) -> UserSkillResponse:
    added = service.add_skill(
        user_id,
        skill_name=body.skill_name,
        category=body.category,
        proficiency=body.proficiency,
    )
    db.commit()
    return _to_skill_response(added)


@router.patch("/{user_id}/skills/{user_skill_id}", response_model=UserSkillResponse)
def update_user_skill(
    user_id: int,
    user_skill_id: int,
    body: UpdateUserSkillRequest,
    _admin: Annotated[JwtTokenPayload, Depends(require_permission(SKILL_MANAGE_ANY))],
    service: Annotated[UserSkillService, Depends(get_user_skill_service)],
    db: Annotated[Session, Depends(get_db_session)],
) -> UserSkillResponse:
    updated = service.update_proficiency(
        user_id,
        user_skill_id,
        proficiency=body.proficiency,
    )
    db.commit()
    return _to_skill_response(updated)


@router.delete(
    "/{user_id}/skills/{user_skill_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def remove_user_skill(
    user_id: int,
    user_skill_id: int,
    _admin: Annotated[JwtTokenPayload, Depends(require_permission(SKILL_MANAGE_ANY))],
    service: Annotated[UserSkillService, Depends(get_user_skill_service)],
    db: Annotated[Session, Depends(get_db_session)],
) -> Response:
    service.remove_skill(user_id, user_skill_id)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
