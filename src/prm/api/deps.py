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
from prm.application.engineer_allocation_service import EngineerAllocationService
from prm.application.engineer_timesheet_service import EngineerTimesheetService
from prm.application.manager_project_service import ManagerProjectService
from prm.application.permission_service import PermissionService
from prm.application.project_management_service import ProjectManagementService
from prm.application.project_milestone_service import ProjectMilestoneService
from prm.application.protocols import LLMClient
from prm.application.resource_dashboard_service import ResourceDashboardService
from prm.application.risk_summary_service import RiskSummaryService
from prm.application.skill_match_service import SkillMatchService
from prm.application.system_config_service import SystemConfigService
from prm.application.team_timesheet_service import TeamTimesheetService
from prm.application.user_management_service import UserManagementService
from prm.application.user_profile_service import UserProfileService
from prm.application.user_skill_service import UserSkillService
from prm.application.utilisation_calculator import UtilisationCalculator
from prm.domain.entities.system_configuration import SystemConfiguration
from prm.domain.enums import Role
from prm.domain.exceptions import UnauthorizedError, ValidationError
from prm.infrastructure.db.repositories import (
    SqlAlchemyAllocationRepository,
    SqlAlchemyMilestoneRepository,
    SqlAlchemyPermissionRepository,
    SqlAlchemyProjectHealthSnapshotRepository,
    SqlAlchemyProjectRepository,
    SqlAlchemySkillRepository,
    SqlAlchemySystemConfigurationRepository,
    SqlAlchemyTimesheetRepository,
    SqlAlchemyUserRepository,
    SqlAlchemyUserSkillRepository,
)
from prm.infrastructure.db.session import get_db_session
from prm.infrastructure.llm.factory import create_llm_client_from_settings
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


def get_user_profile_service(
    db: Annotated[Session, Depends(get_db_session)],
) -> UserProfileService:
    return UserProfileService(
        user_repository=SqlAlchemyUserRepository(db),
        allocation_repository=SqlAlchemyAllocationRepository(db),
    )


def get_user_skill_service(
    db: Annotated[Session, Depends(get_db_session)],
) -> UserSkillService:
    return UserSkillService(
        user_repository=SqlAlchemyUserRepository(db),
        skill_repository=SqlAlchemySkillRepository(db),
        user_skill_repository=SqlAlchemyUserSkillRepository(db),
    )


def get_permission_service(
    db: Annotated[Session, Depends(get_db_session)],
) -> PermissionService:
    return PermissionService(
        user_repository=SqlAlchemyUserRepository(db),
        permission_repository=SqlAlchemyPermissionRepository(db),
    )


def get_project_management_service(
    db: Annotated[Session, Depends(get_db_session)],
) -> ProjectManagementService:
    return ProjectManagementService(
        project_repository=SqlAlchemyProjectRepository(db),
        user_repository=SqlAlchemyUserRepository(db),
        milestone_repository=SqlAlchemyMilestoneRepository(db),
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
        user_repository=SqlAlchemyUserRepository(db),
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


def require_engineer(
    current_user: Annotated[JwtTokenPayload, Depends(get_current_user)],
) -> JwtTokenPayload:
    if current_user.role != Role.ENGINEER:
        raise UnauthorizedError(
            f"Role {current_user.role.value} is not permitted for this action."
        )
    return current_user


def require_permission(permission_code: str):
    """Factory: assert the current user has a RBAC permission code."""

    def _checker(
        current_user: Annotated[JwtTokenPayload, Depends(get_current_user)],
        permission_service: Annotated[PermissionService, Depends(get_permission_service)],
    ) -> JwtTokenPayload:
        permission_service.assert_permission(current_user.user_id, permission_code)
        return current_user

    return _checker


def get_engineer_timesheet_service(
    db: Annotated[Session, Depends(get_db_session)],
) -> EngineerTimesheetService:
    return EngineerTimesheetService(
        user_repository=SqlAlchemyUserRepository(db),
        allocation_repository=SqlAlchemyAllocationRepository(db),
        project_repository=SqlAlchemyProjectRepository(db),
        timesheet_repository=SqlAlchemyTimesheetRepository(db),
        config_repository=SqlAlchemySystemConfigurationRepository(db),
    )


def get_engineer_allocation_service(
    db: Annotated[Session, Depends(get_db_session)],
) -> EngineerAllocationService:
    return EngineerAllocationService(
        user_repository=SqlAlchemyUserRepository(db),
        allocation_repository=SqlAlchemyAllocationRepository(db),
        project_repository=SqlAlchemyProjectRepository(db),
        config_repository=SqlAlchemySystemConfigurationRepository(db),
    )


def get_allocation_service(
    db: Annotated[Session, Depends(get_db_session)],
) -> AllocationService:
    project_repository = SqlAlchemyProjectRepository(db)
    allocation_repository = SqlAlchemyAllocationRepository(db)
    return AllocationService(
        allocation_repository=allocation_repository,
        user_repository=SqlAlchemyUserRepository(db),
        project_repository=project_repository,
        authorization=AuthorizationService(project_repository),
        utilisation=UtilisationCalculator(allocation_repository),
    )


def get_resource_dashboard_service(
    db: Annotated[Session, Depends(get_db_session)],
) -> ResourceDashboardService:
    return ResourceDashboardService(
        user_repository=SqlAlchemyUserRepository(db),
        user_skill_repository=SqlAlchemyUserSkillRepository(db),
        skill_repository=SqlAlchemySkillRepository(db),
        allocation_repository=SqlAlchemyAllocationRepository(db),
        project_repository=SqlAlchemyProjectRepository(db),
        timesheet_repository=SqlAlchemyTimesheetRepository(db),
    )


def get_manager_project_service(
    db: Annotated[Session, Depends(get_db_session)],
) -> ManagerProjectService:
    project_repository = SqlAlchemyProjectRepository(db)
    return ManagerProjectService(
        project_repository=project_repository,
        milestone_repository=SqlAlchemyMilestoneRepository(db),
        allocation_repository=SqlAlchemyAllocationRepository(db),
        user_repository=SqlAlchemyUserRepository(db),
        health_snapshot_repository=SqlAlchemyProjectHealthSnapshotRepository(db),
        authorization=AuthorizationService(project_repository),
    )


def get_team_timesheet_service(
    db: Annotated[Session, Depends(get_db_session)],
) -> TeamTimesheetService:
    return TeamTimesheetService(
        allocation_repository=SqlAlchemyAllocationRepository(db),
        user_repository=SqlAlchemyUserRepository(db),
        project_repository=SqlAlchemyProjectRepository(db),
        timesheet_repository=SqlAlchemyTimesheetRepository(db),
    )


def _require_system_configuration(session: Session) -> SystemConfiguration:
    repository = SqlAlchemySystemConfigurationRepository(session)
    config = repository.find_singleton()
    if config is None:
        return repository.create_with_defaults()
    return config


def get_llm_client(
    db: Annotated[Session, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> LLMClient:
    config = _require_system_configuration(db)
    if not config.has_llm_api_key():
        raise ValidationError("LLM API key is not configured.")

    assert config.llm_api_key_encrypted is not None
    api_key = FernetLlmApiKeyProtector(settings.jwt_secret_key).decrypt(
        config.llm_api_key_encrypted
    )
    return create_llm_client_from_settings(config.llm_provider, api_key, settings)


def get_skill_match_service(
    db: Annotated[Session, Depends(get_db_session)],
    llm_client: Annotated[LLMClient, Depends(get_llm_client)],
) -> SkillMatchService:
    project_repository = SqlAlchemyProjectRepository(db)
    config = _require_system_configuration(db)
    return SkillMatchService(
        user_repository=SqlAlchemyUserRepository(db),
        user_skill_repository=SqlAlchemyUserSkillRepository(db),
        skill_repository=SqlAlchemySkillRepository(db),
        timesheet_repository=SqlAlchemyTimesheetRepository(db),
        authorization=AuthorizationService(project_repository),
        llm_client=llm_client,
        max_weekly_hours=config.max_weekly_hours,
    )


def get_risk_summary_service(
    db: Annotated[Session, Depends(get_db_session)],
    llm_client: Annotated[LLMClient, Depends(get_llm_client)],
) -> RiskSummaryService:
    project_repository = SqlAlchemyProjectRepository(db)
    config = _require_system_configuration(db)
    return RiskSummaryService(
        project_repository=project_repository,
        milestone_repository=SqlAlchemyMilestoneRepository(db),
        allocation_repository=SqlAlchemyAllocationRepository(db),
        user_repository=SqlAlchemyUserRepository(db),
        health_snapshot_repository=SqlAlchemyProjectHealthSnapshotRepository(db),
        timesheet_repository=SqlAlchemyTimesheetRepository(db),
        authorization=AuthorizationService(project_repository),
        llm_client=llm_client,
        max_weekly_hours=config.max_weekly_hours,
    )
