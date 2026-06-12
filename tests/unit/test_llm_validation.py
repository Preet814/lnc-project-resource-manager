"""Unit tests for LLM URL and model validation."""

import pytest

from prm.domain.constants import (
    DEFAULT_GEMINI_BASE_URL,
    DEFAULT_GEMMA_BASE_URL,
    DEFAULT_GROQ_BASE_URL,
)
from prm.domain.enums import LLMProvider
from prm.domain.exceptions import ValidationError
from prm.infrastructure.llm.validation import validate_llm_base_url, validate_llm_model


def test_validate_llm_base_url_accepts_default_gemini_url() -> None:
    assert (
        validate_llm_base_url(LLMProvider.GEMINI, DEFAULT_GEMINI_BASE_URL)
        == DEFAULT_GEMINI_BASE_URL
    )


def test_validate_llm_base_url_strips_trailing_slash() -> None:
    assert (
        validate_llm_base_url(LLMProvider.GEMINI, f"{DEFAULT_GEMINI_BASE_URL}/")
        == DEFAULT_GEMINI_BASE_URL
    )


def test_validate_llm_base_url_rejects_http() -> None:
    with pytest.raises(ValidationError, match="must use HTTPS"):
        validate_llm_base_url(
            LLMProvider.GEMINI,
            "http://generativelanguage.googleapis.com/v1beta",
        )


def test_validate_llm_base_url_rejects_wrong_host_for_provider() -> None:
    with pytest.raises(ValidationError, match="Gemini base URL host is not allowed"):
        validate_llm_base_url(LLMProvider.GEMINI, DEFAULT_GROQ_BASE_URL)


def test_validate_llm_model_rejects_blank_value() -> None:
    with pytest.raises(ValidationError, match="LLM model is required"):
        validate_llm_model("   ")


def test_validate_llm_model_accepts_non_empty_name() -> None:
    assert validate_llm_model(" gemini-1.5-flash ") == "gemini-1.5-flash"


def test_validate_llm_base_url_accepts_http_for_gemma() -> None:
    assert (
        validate_llm_base_url(LLMProvider.GEMMA, DEFAULT_GEMMA_BASE_URL)
        == DEFAULT_GEMMA_BASE_URL
    )
