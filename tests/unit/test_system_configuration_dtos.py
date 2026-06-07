"""Unit tests for system configuration DTOs."""

from prm.domain.dtos import SystemConfigurationSummary
from prm.domain.enums import LLMProvider


def test_system_configuration_summary_fields() -> None:
    summary = SystemConfigurationSummary(
        llm_provider=LLMProvider.GEMINI,
        llm_api_key_masked="****************************",
        scheduler_interval_hours=4,
        max_weekly_hours=40,
    )

    assert summary.llm_provider == LLMProvider.GEMINI
    assert summary.llm_api_key_masked == "****************************"
    assert summary.scheduler_interval_hours == 4
    assert summary.max_weekly_hours == 40


def test_system_configuration_summary_allows_unset_api_key() -> None:
    summary = SystemConfigurationSummary(
        llm_provider=LLMProvider.GROQ,
        llm_api_key_masked=None,
        scheduler_interval_hours=6,
        max_weekly_hours=35,
    )

    assert summary.llm_provider == LLMProvider.GROQ
    assert summary.llm_api_key_masked is None
    assert summary.max_weekly_hours == 35
