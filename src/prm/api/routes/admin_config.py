"""Admin system-configuration endpoints (BRD §3.5)."""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from prm.api.deps import get_db_session, get_system_config_service, require_admin
from prm.api.schemas.admin_config import (
    SystemConfigurationResponse,
    UpdateLlmApiKeyRequest,
    UpdateLlmProviderRequest,
    UpdateMaxWeeklyHoursRequest,
    UpdateSchedulerIntervalRequest,
)
from prm.application.system_config_service import SystemConfigService
from prm.domain.dtos import SystemConfigurationSummary
from prm.infrastructure.security.jwt import JwtTokenPayload

router = APIRouter(prefix="/admin/config", tags=["admin-config"])


def _to_configuration_response(
    summary: SystemConfigurationSummary,
) -> SystemConfigurationResponse:
    return SystemConfigurationResponse(
        llm_provider=summary.llm_provider,
        llm_api_key_masked=summary.llm_api_key_masked,
        scheduler_interval_hours=summary.scheduler_interval_hours,
        max_weekly_hours=summary.max_weekly_hours,
    )


@router.get("", response_model=SystemConfigurationResponse)
def get_configuration(
    _admin: Annotated[JwtTokenPayload, Depends(require_admin)],
    service: Annotated[SystemConfigService, Depends(get_system_config_service)],
) -> SystemConfigurationResponse:
    return _to_configuration_response(service.get_configuration())


@router.patch("/llm-api-key", response_model=SystemConfigurationResponse)
def update_llm_api_key(
    body: UpdateLlmApiKeyRequest,
    _admin: Annotated[JwtTokenPayload, Depends(require_admin)],
    service: Annotated[SystemConfigService, Depends(get_system_config_service)],
    db: Annotated[Session, Depends(get_db_session)],
) -> SystemConfigurationResponse:
    summary = service.update_llm_api_key(body.api_key)
    db.commit()
    return _to_configuration_response(summary)


@router.patch("/llm-provider", response_model=SystemConfigurationResponse)
def update_llm_provider(
    body: UpdateLlmProviderRequest,
    _admin: Annotated[JwtTokenPayload, Depends(require_admin)],
    service: Annotated[SystemConfigService, Depends(get_system_config_service)],
    db: Annotated[Session, Depends(get_db_session)],
) -> SystemConfigurationResponse:
    summary = service.update_llm_provider(body.provider)
    db.commit()
    return _to_configuration_response(summary)


@router.patch("/scheduler-interval", response_model=SystemConfigurationResponse)
def update_scheduler_interval(
    body: UpdateSchedulerIntervalRequest,
    _admin: Annotated[JwtTokenPayload, Depends(require_admin)],
    service: Annotated[SystemConfigService, Depends(get_system_config_service)],
    db: Annotated[Session, Depends(get_db_session)],
) -> SystemConfigurationResponse:
    summary = service.update_scheduler_interval_hours(body.scheduler_interval_hours)
    db.commit()
    return _to_configuration_response(summary)


@router.patch("/max-weekly-hours", response_model=SystemConfigurationResponse)
def update_max_weekly_hours(
    body: UpdateMaxWeeklyHoursRequest,
    _admin: Annotated[JwtTokenPayload, Depends(require_admin)],
    service: Annotated[SystemConfigService, Depends(get_system_config_service)],
    db: Annotated[Session, Depends(get_db_session)],
) -> SystemConfigurationResponse:
    summary = service.update_max_weekly_hours(body.max_weekly_hours)
    db.commit()
    return _to_configuration_response(summary)
