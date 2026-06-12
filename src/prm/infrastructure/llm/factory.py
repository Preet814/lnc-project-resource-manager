"""Construct LLMClient implementations from system configuration."""

from typing import TYPE_CHECKING

from prm.application.protocols import LLMClient
from prm.domain.enums import LLMProvider
from prm.domain.exceptions import ValidationError
from prm.infrastructure.llm.gemini_client import GeminiClient
from prm.infrastructure.llm.gemma_client import GemmaClient
from prm.infrastructure.llm.groq_client import GroqClient
from prm.infrastructure.llm.validation import validate_llm_base_url, validate_llm_model

if TYPE_CHECKING:
    from prm.api.settings import Settings


def create_llm_client(
    provider: LLMProvider,
    api_key: str,
    *,
    base_url: str,
    model: str,
) -> LLMClient:
    """Factory for Gemini and Groq adapters (DESIGN.md)."""
    normalized_key = api_key.strip()
    if not normalized_key:
        raise ValidationError("LLM API key is required.")

    validated_url = validate_llm_base_url(provider, base_url)
    validated_model = validate_llm_model(model)

    if provider is LLMProvider.GEMINI:
        return GeminiClient(
            normalized_key,
            base_url=validated_url,
            model=validated_model,
        )
    if provider is LLMProvider.GROQ:
        return GroqClient(
            normalized_key,
            base_url=validated_url,
            model=validated_model,
        )
    if provider is LLMProvider.GEMMA:
        return GemmaClient(
            normalized_key,
            base_url=validated_url,
            model=validated_model,
        )
    raise ValidationError(f"Unknown LLM provider: {provider}")


def create_llm_client_from_settings(
    provider: LLMProvider,
    api_key: str,
    settings: "Settings",
) -> LLMClient:
    """Build an LLM client using provider-specific URL and model from Settings."""
    if provider is LLMProvider.GEMINI:
        return create_llm_client(
            provider,
            api_key,
            base_url=settings.gemini_base_url,
            model=settings.gemini_model,
        )
    if provider is LLMProvider.GROQ:
        return create_llm_client(
            provider,
            api_key,
            base_url=settings.groq_base_url,
            model=settings.groq_model,
        )
    if provider is LLMProvider.GEMMA:
        return create_llm_client(
            provider,
            api_key,
            base_url=settings.gemma_base_url,
            model=settings.gemma_model,
        )
    raise ValidationError(f"Unknown LLM provider: {provider}")
