"""Unit tests for SystemConfiguration domain entity."""

from prm.domain.entities.system_configuration import SystemConfiguration
from prm.domain.enums import LLMProvider


def _config(*, llm_api_key_encrypted: str | None = "encrypted-key") -> SystemConfiguration:
    return SystemConfiguration(
        id=1,
        llm_provider=LLMProvider.GEMINI,
        llm_api_key_encrypted=llm_api_key_encrypted,
        scheduler_interval_hours=4,
        max_weekly_hours=40,
    )


def test_get_max_weekly_hours() -> None:
    assert _config().get_max_weekly_hours() == 40


def test_has_llm_api_key_when_set() -> None:
    assert _config(llm_api_key_encrypted="encrypted-key").has_llm_api_key() is True


def test_has_llm_api_key_when_missing() -> None:
    assert _config(llm_api_key_encrypted=None).has_llm_api_key() is False
    assert _config(llm_api_key_encrypted="").has_llm_api_key() is False
