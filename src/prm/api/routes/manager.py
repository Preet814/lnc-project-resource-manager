"""Manager resource dashboard and allocation endpoints (BRD §4.1, §4.2)."""

from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from prm.api.deps import (
    get_allocation_service,
    get_db_session,
    get_resource_dashboard_service,
    require_manager,
)
from prm.api.schemas.admin_allocations import AllocationSummaryResponse
from prm.api.schemas.manager import (
    ActiveEmployeeResponse,
    BenchEmployeeResponse,
    CreateAllocationRequest,
    EmployeeAllocationDetailResponse,
    EmployeeResourceDetailResponse,
    EndAllocationRequest,
    ManagerAllocationResponse,
    ProjectAllocationListResponse,
    ResourceDashboardResponse,
)
from prm.application.allocation_service import AllocationService
from prm.application.resource_dashboard_service import ResourceDashboardService
from prm.domain.dtos import (
    AllocationSummary,
    EmployeeResourceDetail,
    ResourceDashboardResult,
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
