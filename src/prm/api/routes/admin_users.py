"""Admin user-management endpoints (BRD §3.4)."""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from prm.api.deps import (
    get_db_session,
    get_user_management_service,
    require_admin,
    require_permission,
)
from prm.domain.permission_codes import USER_CREATE, USER_DEACTIVATE, USER_RESET_PASSWORD
from prm.api.schemas.admin_users import (
    CreateUserRequest,
    ResetPasswordRequest,
    UserListResponse,
    UserResponse,
    UserSummaryResponse,
)
from prm.application.user_management_service import UserManagementService
from prm.domain.dtos import UserListResult
from prm.domain.entities.user import User
from prm.infrastructure.security.jwt import JwtTokenPayload

router = APIRouter(prefix="/admin/users", tags=["admin-users"])


def _to_user_response(user: User) -> UserResponse:
    return UserResponse(
        id=user.id,
        full_name=user.full_name,
        username=user.username,
        email=user.email,
        role=user.role,
        account_status=user.account_status,
        force_password_change=user.force_password_change,
    )


def _to_user_list_response(result: UserListResult) -> UserListResponse:
    return UserListResponse(
        users=[
            UserSummaryResponse(
                id=summary.id,
                username=summary.username,
                full_name=summary.full_name,
                role=summary.role,
                account_status=summary.account_status,
                department=summary.department,
                designation=summary.designation,
            )
            for summary in result.users
        ],
        total=result.total,
        active_count=result.active_count,
        inactive_count=result.inactive_count,
    )


@router.post("", response_model=UserResponse, status_code=201)
def create_user(
    body: CreateUserRequest,
    _admin: Annotated[JwtTokenPayload, Depends(require_permission(USER_CREATE))],
    service: Annotated[UserManagementService, Depends(get_user_management_service)],
    db: Annotated[Session, Depends(get_db_session)],
) -> UserResponse:
    created = service.create_user(
        full_name=body.full_name,
        email=body.email,
        username=body.username,
        temporary_password=body.temporary_password,
        role=body.role,
        department=body.department,
        designation=body.designation,
    )
    db.commit()
    return _to_user_response(created)


@router.get("", response_model=UserListResponse)
def list_users(
    _admin: Annotated[JwtTokenPayload, Depends(require_admin)],
    service: Annotated[UserManagementService, Depends(get_user_management_service)],
) -> UserListResponse:
    return _to_user_list_response(service.list_users())


@router.post("/reset-password", response_model=UserResponse)
def reset_password(
    body: ResetPasswordRequest,
    _admin: Annotated[JwtTokenPayload, Depends(require_permission(USER_RESET_PASSWORD))],
    service: Annotated[UserManagementService, Depends(get_user_management_service)],
    db: Annotated[Session, Depends(get_db_session)],
) -> UserResponse:
    updated = service.reset_password(
        body.identifier,
        temporary_password=body.temporary_password,
    )
    db.commit()
    return _to_user_response(updated)


@router.post("/{user_id}/reactivate", response_model=UserResponse)
def reactivate_user(
    user_id: int,
    _admin: Annotated[JwtTokenPayload, Depends(require_admin)],
    service: Annotated[UserManagementService, Depends(get_user_management_service)],
    db: Annotated[Session, Depends(get_db_session)],
) -> UserResponse:
    reactivated = service.reactivate_user(user_id)
    db.commit()
    return _to_user_response(reactivated)


@router.post("/{user_id}/deactivate", response_model=UserResponse)
def deactivate_user(
    user_id: int,
    admin: Annotated[JwtTokenPayload, Depends(require_permission(USER_DEACTIVATE))],
    service: Annotated[UserManagementService, Depends(get_user_management_service)],
    db: Annotated[Session, Depends(get_db_session)],
) -> UserResponse:
    deactivated = service.deactivate_user(user_id, actor_user_id=admin.user_id)
    db.commit()
    return _to_user_response(deactivated)
