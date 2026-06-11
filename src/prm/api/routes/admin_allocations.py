"""Admin allocation-view endpoints (BRD §3.3)."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from prm.api.deps import get_allocation_view_service, require_admin
from prm.api.schemas.admin_allocations import AllocationListResponse, AllocationSummaryResponse
from prm.application.allocation_view_service import AllocationViewService
from prm.domain.dtos import AllocationListResult
from prm.infrastructure.security.jwt import JwtTokenPayload

router = APIRouter(prefix="/admin/allocations", tags=["admin-allocations"])


def _to_allocation_list_response(result: AllocationListResult) -> AllocationListResponse:
    return AllocationListResponse(
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
            for summary in result.allocations
        ],
        total=result.total,
    )


@router.get("", response_model=AllocationListResponse)
def list_allocations(
    _admin: Annotated[JwtTokenPayload, Depends(require_admin)],
    service: Annotated[AllocationViewService, Depends(get_allocation_view_service)],
    user_id: Annotated[int | None, Query()] = None,
    project_id: Annotated[int | None, Query()] = None,
) -> AllocationListResponse:
    return _to_allocation_list_response(
        service.list_allocations(
            user_id=user_id,
            project_id=project_id,
        ),
    )
