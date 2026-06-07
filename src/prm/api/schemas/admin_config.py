"""Admin system-configuration API request and response schemas."""

from pydantic import BaseModel, Field

from prm.domain.enums import LLMProvider


class SystemConfigurationResponse(BaseModel):
    llm_provider: LLMProvider
    llm_api_key_masked: str | None
    scheduler_interval_hours: int
    max_weekly_hours: int


class UpdateLlmApiKeyRequest(BaseModel):
    api_key: str = Field(min_length=1)


class UpdateLlmProviderRequest(BaseModel):
    provider: LLMProvider


class UpdateSchedulerIntervalRequest(BaseModel):
    scheduler_interval_hours: int = Field(ge=1, le=168)


class UpdateMaxWeeklyHoursRequest(BaseModel):
    max_weekly_hours: int = Field(ge=1, le=168)
