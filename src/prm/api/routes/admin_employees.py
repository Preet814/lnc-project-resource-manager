"""Admin employee-management endpoints (BRD §3.1)."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from prm.api.deps import (
    get_db_session,
    get_employee_management_service,
    get_employee_skill_service,
    require_admin,
)
from prm.api.schemas.admin_employees import (
    AddEmployeeSkillRequest,
    AssignManagerRequest,
    CreateEmployeeRequest,
    EmployeeListResponse,
    EmployeeResponse,
    EmployeeSkillListResponse,
    EmployeeSkillResponse,
    EmployeeSummaryResponse,
    UpdateEmployeeRequest,
    UpdateEmployeeSkillRequest,
)
from prm.application.employee_management_service import EmployeeManagementService
from prm.application.employee_skill_service import EmployeeSkillService
from prm.domain.dtos import EmployeeListResult, EmployeeSkillDetail
from prm.domain.entities.employee import Employee
from prm.domain.enums import EmployeeWorkStatus
from prm.infrastructure.security.jwt import JwtTokenPayload

router = APIRouter(prefix="/admin/employees", tags=["admin-employees"])


def _to_employee_response(employee: Employee) -> EmployeeResponse:
    return EmployeeResponse(
        id=employee.id,
        user_id=employee.user_id,
        manager_id=employee.manager_id,
        full_name=employee.full_name,
        email=employee.email,
        department=employee.department,
        designation=employee.designation,
        work_status=employee.work_status,
        is_active=employee.is_active,
        current_utilisation_percent=employee.current_utilisation_percent,
        created_at=employee.created_at,
    )


def _to_employee_list_response(result: EmployeeListResult) -> EmployeeListResponse:
    return EmployeeListResponse(
        employees=[
            EmployeeSummaryResponse(
                id=summary.id,
                full_name=summary.full_name,
                department=summary.department,
                work_status=summary.work_status,
                is_active=summary.is_active,
            )
            for summary in result.employees
        ],
        total=result.total,
        allocated_count=result.allocated_count,
        bench_count=result.bench_count,
    )


def _to_skill_response(detail: EmployeeSkillDetail) -> EmployeeSkillResponse:
    return EmployeeSkillResponse(
        employee_skill_id=detail.employee_skill_id,
        skill_id=detail.skill_id,
        skill_name=detail.skill_name,
        category=detail.category,
        proficiency=detail.proficiency,
        assigned_at=detail.assigned_at,
    )


def _to_skill_list_response(
    skills: tuple[EmployeeSkillDetail, ...],
) -> EmployeeSkillListResponse:
    return EmployeeSkillListResponse(
        skills=[_to_skill_response(skill) for skill in skills],
    )


@router.post("", response_model=EmployeeResponse, status_code=status.HTTP_201_CREATED)
def create_employee(
    body: CreateEmployeeRequest,
    _admin: Annotated[JwtTokenPayload, Depends(require_admin)],
    service: Annotated[EmployeeManagementService, Depends(get_employee_management_service)],
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


@router.get("", response_model=EmployeeListResponse)
def list_employees(
    _admin: Annotated[JwtTokenPayload, Depends(require_admin)],
    service: Annotated[EmployeeManagementService, Depends(get_employee_management_service)],
    work_status: EmployeeWorkStatus | None = None,
    department: str | None = None,
    active_only: Annotated[bool, Query()] = True,
) -> EmployeeListResponse:
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
    _admin: Annotated[JwtTokenPayload, Depends(require_admin)],
    service: Annotated[EmployeeManagementService, Depends(get_employee_management_service)],
    db: Annotated[Session, Depends(get_db_session)],
) -> EmployeeResponse:
    updated = service.assign_manager(
        employee_user_id=body.employee_user_id,
        manager_user_id=body.manager_user_id,
    )
    db.commit()
    return _to_employee_response(updated)


@router.get("/{employee_id}", response_model=EmployeeResponse)
def get_employee(
    employee_id: int,
    _admin: Annotated[JwtTokenPayload, Depends(require_admin)],
    service: Annotated[EmployeeManagementService, Depends(get_employee_management_service)],
) -> EmployeeResponse:
    return _to_employee_response(service.get_employee(employee_id))


@router.patch("/{employee_id}", response_model=EmployeeResponse)
def update_employee(
    employee_id: int,
    body: UpdateEmployeeRequest,
    _admin: Annotated[JwtTokenPayload, Depends(require_admin)],
    service: Annotated[EmployeeManagementService, Depends(get_employee_management_service)],
    db: Annotated[Session, Depends(get_db_session)],
) -> EmployeeResponse:
    updated = service.update_employee(
        employee_id,
        full_name=body.full_name,
        email=body.email,
        department=body.department,
        designation=body.designation,
    )
    db.commit()
    return _to_employee_response(updated)


@router.post("/{employee_id}/deactivate", response_model=EmployeeResponse)
def deactivate_employee(
    employee_id: int,
    _admin: Annotated[JwtTokenPayload, Depends(require_admin)],
    service: Annotated[EmployeeManagementService, Depends(get_employee_management_service)],
    db: Annotated[Session, Depends(get_db_session)],
) -> EmployeeResponse:
    deactivated = service.deactivate_employee(employee_id)
    db.commit()
    return _to_employee_response(deactivated)


@router.get("/{employee_id}/skills", response_model=EmployeeSkillListResponse)
def list_employee_skills(
    employee_id: int,
    _admin: Annotated[JwtTokenPayload, Depends(require_admin)],
    service: Annotated[EmployeeSkillService, Depends(get_employee_skill_service)],
) -> EmployeeSkillListResponse:
    return _to_skill_list_response(service.list_skills(employee_id))


@router.post(
    "/{employee_id}/skills",
    response_model=EmployeeSkillResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_employee_skill(
    employee_id: int,
    body: AddEmployeeSkillRequest,
    _admin: Annotated[JwtTokenPayload, Depends(require_admin)],
    service: Annotated[EmployeeSkillService, Depends(get_employee_skill_service)],
    db: Annotated[Session, Depends(get_db_session)],
) -> EmployeeSkillResponse:
    added = service.add_skill(
        employee_id,
        skill_name=body.skill_name,
        category=body.category,
        proficiency=body.proficiency,
    )
    db.commit()
    return _to_skill_response(added)


@router.patch("/{employee_id}/skills/{employee_skill_id}", response_model=EmployeeSkillResponse)
def update_employee_skill(
    employee_id: int,
    employee_skill_id: int,
    body: UpdateEmployeeSkillRequest,
    _admin: Annotated[JwtTokenPayload, Depends(require_admin)],
    service: Annotated[EmployeeSkillService, Depends(get_employee_skill_service)],
    db: Annotated[Session, Depends(get_db_session)],
) -> EmployeeSkillResponse:
    updated = service.update_proficiency(
        employee_id,
        employee_skill_id,
        proficiency=body.proficiency,
    )
    db.commit()
    return _to_skill_response(updated)


@router.delete(
    "/{employee_id}/skills/{employee_skill_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def remove_employee_skill(
    employee_id: int,
    employee_skill_id: int,
    _admin: Annotated[JwtTokenPayload, Depends(require_admin)],
    service: Annotated[EmployeeSkillService, Depends(get_employee_skill_service)],
    db: Annotated[Session, Depends(get_db_session)],
) -> Response:
    service.remove_skill(employee_id, employee_skill_id)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
