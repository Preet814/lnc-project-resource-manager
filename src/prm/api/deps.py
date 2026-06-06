"""FastAPI dependency injection wiring."""

from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from prm.api.settings import Settings, get_settings
from prm.application.auth_service import AuthService
from prm.infrastructure.db.repositories import SqlAlchemyUserRepository
from prm.infrastructure.db.session import get_db_session
from prm.infrastructure.security.jwt import JwtTokenPayload, JwtTokenService
from prm.infrastructure.security.password import BcryptPasswordHasher

_bearer_scheme = HTTPBearer(auto_error=True)


def get_token_service(settings: Annotated[Settings, Depends(get_settings)]) -> JwtTokenService:
    return JwtTokenService(
        secret_key=settings.jwt_secret_key,
        expire_minutes=settings.jwt_expire_minutes,
    )


def get_auth_service(
    db: Annotated[Session, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> AuthService:
    return AuthService(
        user_repository=SqlAlchemyUserRepository(db),
        password_hasher=BcryptPasswordHasher(),
        token_service=JwtTokenService(
            secret_key=settings.jwt_secret_key,
            expire_minutes=settings.jwt_expire_minutes,
        ),
    )


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(_bearer_scheme)],
    token_service: Annotated[JwtTokenService, Depends(get_token_service)],
) -> JwtTokenPayload:
    return token_service.decode_access_token(credentials.credentials)
