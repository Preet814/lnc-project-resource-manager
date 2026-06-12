"""Unit tests for create_llm_client factory."""

import pytest

from prm.domain.constants import (
    DEFAULT_GEMINI_BASE_URL,
    DEFAULT_GEMINI_MODEL,
    DEFAULT_GEMMA_BASE_URL,
    DEFAULT_GEMMA_MODEL,
    DEFAULT_GROQ_BASE_URL,
    DEFAULT_GROQ_MODEL,
)
from prm.domain.enums import LLMProvider
from prm.domain.exceptions import ValidationError
from prm.infrastructure.llm.factory import create_llm_client, create_llm_client_from_settings
from prm.infrastructure.llm.gemini_client import GeminiClient
from prm.infrastructure.llm.gemma_client import GemmaClient
from prm.infrastructure.llm.groq_client import GroqClient


def test_create_gemini_client() -> None:
    client = create_llm_client(
        LLMProvider.GEMINI,
        "gemini-key",
        base_url=DEFAULT_GEMINI_BASE_URL,
        model=DEFAULT_GEMINI_MODEL,
    )

    assert isinstance(client, GeminiClient)


def test_create_gemma_client() -> None:
    client = create_llm_client(
        LLMProvider.GEMMA,
        "gemma-key",
        base_url=DEFAULT_GEMMA_BASE_URL,
        model=DEFAULT_GEMMA_MODEL,
    )

    assert isinstance(client, GemmaClient)


def test_create_groq_client() -> None:
    client = create_llm_client(
        LLMProvider.GROQ,
        "groq-key",
        base_url=DEFAULT_GROQ_BASE_URL,
        model=DEFAULT_GROQ_MODEL,
    )

    assert isinstance(client, GroqClient)


def test_create_llm_client_rejects_blank_api_key() -> None:
    with pytest.raises(ValidationError, match="LLM API key is required"):
        create_llm_client(
            LLMProvider.GEMINI,
            "   ",
            base_url=DEFAULT_GEMINI_BASE_URL,
            model=DEFAULT_GEMINI_MODEL,
        )


def test_create_llm_client_rejects_invalid_base_url() -> None:
    with pytest.raises(ValidationError, match="host is not allowed"):
        create_llm_client(
            LLMProvider.GEMINI,
            "gemini-key",
            base_url="https://evil.example.com/v1beta",
            model=DEFAULT_GEMINI_MODEL,
        )


def test_create_llm_client_from_settings_uses_gemini_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JWT_SECRET_KEY", "test-secret-key")
    monkeypatch.setenv("BOOTSTRAP_ADMIN_USERNAME", "admin")
    monkeypatch.setenv("BOOTSTRAP_ADMIN_PASSWORD", "AdminPass1")
    monkeypatch.setenv("BOOTSTRAP_ADMIN_FULL_NAME", "Admin User")
    monkeypatch.setenv("BOOTSTRAP_ADMIN_EMAIL", "admin@example.test")
    monkeypatch.setenv("GEMINI_MODEL", "gemini-2.0-flash")

    from prm.api.settings import get_settings

    get_settings.cache_clear()
    settings = get_settings()
    client = create_llm_client_from_settings(LLMProvider.GEMINI, "gemini-key", settings)

    assert isinstance(client, GeminiClient)
    assert client._model == "gemini-2.0-flash"
    get_settings.cache_clear()
