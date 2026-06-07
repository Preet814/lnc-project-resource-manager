"""FastAPI dependency injection wiring."""

from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from prm.api.settings import Settings, get_settings
from prm.application.allocation_service import AllocationService
from prm.application.allocation_view_service import AllocationViewService
from prm.application.auth_service import AuthService
from prm.application.authorization_service import AuthorizationService
from prm.application.employee_management_service import EmployeeManagementService
from prm.application.employee_skill_service import EmployeeSkillService
from prm.application.project_management_service import ProjectManagementService
from prm.application.project_milestone_service import ProjectMilestoneService
from prm.application.resource_dashboard_service import ResourceDashboardService
from prm.application.system_config_service import SystemConfigService
from prm.application.user_management_service import UserManagementService
from prm.application.utilisation_calculator import UtilisationCalculator
from prm.domain.enums import Role
from prm.domain.exceptions import UnauthorizedError
from prm.infrastructure.db.repositories import (
    SqlAlchemyAllocationRepository,
    SqlAlchemyEmployeeRepository,
    SqlAlchemyEmployeeSkillRepository,
    SqlAlchemyMilestoneRepository,
    SqlAlchemyProjectRepository,
    SqlAlchemySkillRepository,
    SqlAlchemySystemConfigurationRepository,
    SqlAlchemyTimesheetRepository,
    SqlAlchemyUserRepository,
)
from prm.infrastructure.db.session import get_db_session
from prm.infrastructure.security.jwt import JwtTokenPayload, JwtTokenService
from prm.infrastructure.security.llm_api_key import FernetLlmApiKeyProtector
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


def get_user_management_service(
    db: Annotated[Session, Depends(get_db_session)],
) -> UserManagementService:
    return UserManagementService(
        user_repository=SqlAlchemyUserRepository(db),
        password_hasher=BcryptPasswordHasher(),
    )


def get_employee_management_service(
    db: Annotated[Session, Depends(get_db_session)],
) -> EmployeeManagementService:
    return EmployeeManagementService(
        employee_repository=SqlAlchemyEmployeeRepository(db),
        user_repository=SqlAlchemyUserRepository(db),
        allocation_repository=SqlAlchemyAllocationRepository(db),
    )


def get_employee_skill_service(
    db: Annotated[Session, Depends(get_db_session)],
) -> EmployeeSkillService:
    return EmployeeSkillService(
        employee_repository=SqlAlchemyEmployeeRepository(db),
        skill_repository=SqlAlchemySkillRepository(db),
        employee_skill_repository=SqlAlchemyEmployeeSkillRepository(db),
    )


def get_project_management_service(
    db: Annotated[Session, Depends(get_db_session)],
) -> ProjectManagementService:
    return ProjectManagementService(
        project_repository=SqlAlchemyProjectRepository(db),
        user_repository=SqlAlchemyUserRepository(db),
    )


def get_project_milestone_service(
    db: Annotated[Session, Depends(get_db_session)],
) -> ProjectMilestoneService:
    return ProjectMilestoneService(
        project_repository=SqlAlchemyProjectRepository(db),
        milestone_repository=SqlAlchemyMilestoneRepository(db),
    )


def get_allocation_view_service(
    db: Annotated[Session, Depends(get_db_session)],
) -> AllocationViewService:
    return AllocationViewService(
        allocation_repository=SqlAlchemyAllocationRepository(db),
        employee_repository=SqlAlchemyEmployeeRepository(db),
        project_repository=SqlAlchemyProjectRepository(db),
    )


def get_system_config_service(
    db: Annotated[Session, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> SystemConfigService:
    return SystemConfigService(
        config_repository=SqlAlchemySystemConfigurationRepository(db),
        api_key_protector=FernetLlmApiKeyProtector(settings.jwt_secret_key),
    )


def require_admin(
    current_user: Annotated[JwtTokenPayload, Depends(get_current_user)],
) -> JwtTokenPayload:
    if current_user.role != Role.ADMIN:
        raise UnauthorizedError(
            f"Role {current_user.role.value} is not permitted for this action."
        )
    return current_user


def require_manager(
    current_user: Annotated[JwtTokenPayload, Depends(get_current_user)],
) -> JwtTokenPayload:
    if current_user.role != Role.MANAGER:
        raise UnauthorizedError(
            f"Role {current_user.role.value} is not permitted for this action."
        )
    return current_user


def get_allocation_service(
    db: Annotated[Session, Depends(get_db_session)],
) -> AllocationService:
    project_repository = SqlAlchemyProjectRepository(db)
    allocation_repository = SqlAlchemyAllocationRepository(db)
    return AllocationService(
        allocation_repository=allocation_repository,
        employee_repository=SqlAlchemyEmployeeRepository(db),
        project_repository=project_repository,
        authorization=AuthorizationService(project_repository),
        utilisation=UtilisationCalculator(allocation_repository),
    )


def get_resource_dashboard_service(
    db: Annotated[Session, Depends(get_db_session)],
) -> ResourceDashboardService:
    return ResourceDashboardService(
        employee_repository=SqlAlchemyEmployeeRepository(db),
        employee_skill_repository=SqlAlchemyEmployeeSkillRepository(db),
        skill_repository=SqlAlchemySkillRepository(db),
        allocation_repository=SqlAlchemyAllocationRepository(db),
        project_repository=SqlAlchemyProjectRepository(db),
        timesheet_repository=SqlAlchemyTimesheetRepository(db),
    )
