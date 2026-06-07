"""System configuration domain entity."""

from dataclasses import dataclass

from prm.domain.enums import LLMProvider


@dataclass(frozen=True, slots=True)
class SystemConfiguration:
    """Singleton-style system settings row (class diagram «entity»)."""

    id: int
    llm_provider: LLMProvider
    llm_api_key_encrypted: str | None
    scheduler_interval_hours: int
    max_weekly_hours: int

    def get_max_weekly_hours(self) -> int:
        return self.max_weekly_hours

    def has_llm_api_key(self) -> bool:
        return bool(self.llm_api_key_encrypted)
