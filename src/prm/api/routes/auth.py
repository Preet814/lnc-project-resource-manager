"""Authentication endpoints — login and forced password change."""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from prm.api.deps import (
    get_auth_service,
    get_current_user,
    get_db_session,
    get_email_verification_service,
)
from prm.api.schemas.auth import (
    ChangePasswordRequest,
    LoginRequest,
    LoginResponse,
    VerifyEmailConfirmRequest,
)
from prm.application.auth_service import AuthService
from prm.application.email_verification_service import EmailVerificationService
from prm.domain.dtos import LoginResult
from prm.infrastructure.security.jwt import JwtTokenPayload

router = APIRouter(prefix="/auth", tags=["auth"])


def _to_login_response(result: LoginResult) -> LoginResponse:
    return LoginResponse(
        access_token=result.access_token,
        token_type=result.token_type,
        user_id=result.user_id,
        username=result.username,
        full_name=result.full_name,
        role=result.role,
        force_password_change=result.force_password_change,
        email_verified=result.email_verified,
        expires_at=result.expires_at,
    )


@router.post("/login", response_model=LoginResponse)
def login(
    body: LoginRequest,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> LoginResponse:
    result = auth_service.login(body.username, body.password)
    return _to_login_response(result)


@router.post("/change-password", response_model=LoginResponse)
def change_password(
    body: ChangePasswordRequest,
    current_user: Annotated[JwtTokenPayload, Depends(get_current_user)],
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
    db: Annotated[Session, Depends(get_db_session)],
) -> LoginResponse:
    _, result = auth_service.change_password(
        current_user.user_id,
        new_password=body.new_password,
        confirm_password=body.confirm_password,
    )
    db.commit()
    return _to_login_response(result)


@router.post("/verify-email/send-otp", status_code=204)
def send_email_verification_otp(
    current_user: Annotated[JwtTokenPayload, Depends(get_current_user)],
    service: Annotated[EmailVerificationService, Depends(get_email_verification_service)],
    db: Annotated[Session, Depends(get_db_session)],
) -> None:
    service.send_otp(current_user.user_id)
    db.commit()


@router.post("/verify-email/confirm", response_model=LoginResponse)
def confirm_email_verification_otp(
    body: VerifyEmailConfirmRequest,
    current_user: Annotated[JwtTokenPayload, Depends(get_current_user)],
    service: Annotated[EmailVerificationService, Depends(get_email_verification_service)],
    db: Annotated[Session, Depends(get_db_session)],
) -> LoginResponse:
    result = service.confirm_otp(current_user.user_id, otp=body.otp)
    db.commit()
    return _to_login_response(result)
