"""Admin system-configuration use cases (BRD §3.5)."""

from prm.application.protocols import LlmApiKeyProtector, SystemConfigurationRepository
from prm.domain.constants import (
    LLM_API_KEY_MASK,
    MAX_MAX_WEEKLY_HOURS,
    MAX_SCHEDULER_INTERVAL_HOURS,
    MIN_MAX_WEEKLY_HOURS,
    MIN_SCHEDULER_INTERVAL_HOURS,
)
from prm.domain.dtos import SystemConfigurationSummary
from prm.domain.entities.system_configuration import SystemConfiguration
from prm.domain.enums import LLMProvider
from prm.domain.exceptions import ValidationError


class SystemConfigService:
    """Read and update singleton system settings for Admin."""

    def __init__(
        self,
        config_repository: SystemConfigurationRepository,
        api_key_protector: LlmApiKeyProtector,
    ) -> None:
        self._config = config_repository
        self._api_key_protector = api_key_protector

    def get_configuration(self) -> SystemConfigurationSummary:
        return self._to_summary(self._require_config())

    def update_llm_api_key(self, api_key: str) -> SystemConfigurationSummary:
        cleaned = api_key.strip()
        if not cleaned:
            raise ValidationError("LLM API key is required.")

        config = self._require_config()
        encrypted = self._api_key_protector.encrypt(cleaned)
        updated = self._config.update(config.id, llm_api_key_encrypted=encrypted)
        return self._to_summary(updated)

    def update_llm_provider(self, provider: LLMProvider) -> SystemConfigurationSummary:
        config = self._require_config()
        updated = self._config.update(config.id, llm_provider=provider)
        return self._to_summary(updated)

    def update_scheduler_interval_hours(self, hours: int) -> SystemConfigurationSummary:
        self._validate_scheduler_interval_hours(hours)
        config = self._require_config()
        updated = self._config.update(config.id, scheduler_interval_hours=hours)
        return self._to_summary(updated)

    def update_max_weekly_hours(self, hours: int) -> SystemConfigurationSummary:
        self._validate_max_weekly_hours(hours)
        config = self._require_config()
        updated = self._config.update(config.id, max_weekly_hours=hours)
        return self._to_summary(updated)

    def _require_config(self) -> SystemConfiguration:
        config = self._config.find_singleton()
        if config is None:
            config = self._config.create_with_defaults()
        return config

    def _to_summary(self, config: SystemConfiguration) -> SystemConfigurationSummary:
        return SystemConfigurationSummary(
            llm_provider=config.llm_provider,
            llm_api_key_masked=LLM_API_KEY_MASK if config.has_llm_api_key() else None,
            scheduler_interval_hours=config.scheduler_interval_hours,
            max_weekly_hours=config.max_weekly_hours,
        )

    @staticmethod
    def _validate_scheduler_interval_hours(hours: int) -> None:
        if hours < MIN_SCHEDULER_INTERVAL_HOURS or hours > MAX_SCHEDULER_INTERVAL_HOURS:
            raise ValidationError(
                f"Scheduler interval must be between {MIN_SCHEDULER_INTERVAL_HOURS} "
                f"and {MAX_SCHEDULER_INTERVAL_HOURS} hours."
            )

    @staticmethod
    def _validate_max_weekly_hours(hours: int) -> None:
        if hours < MIN_MAX_WEEKLY_HOURS or hours > MAX_MAX_WEEKLY_HOURS:
            raise ValidationError(
                f"Max weekly hours must be between {MIN_MAX_WEEKLY_HOURS} "
                f"and {MAX_MAX_WEEKLY_HOURS}."
            )
