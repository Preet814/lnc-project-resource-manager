"""Validate LLM base URLs and model names loaded from environment."""

from urllib.parse import urlparse

from prm.domain.enums import LLMProvider
from prm.domain.exceptions import ValidationError

ALLOWED_GEMINI_HOSTS = frozenset({"generativelanguage.googleapis.com"})
ALLOWED_GROQ_HOSTS = frozenset({"api.groq.com"})


def validate_llm_base_url(provider: LLMProvider, base_url: str) -> str:
    """Ensure the base URL is HTTPS and points at an allowed vendor host."""
    cleaned = base_url.strip().rstrip("/")
    if not cleaned:
        raise ValidationError("LLM base URL is required.")

    parsed = urlparse(cleaned)
    if parsed.scheme != "https":
        raise ValidationError("LLM base URL must use HTTPS.")
    if not parsed.netloc:
        raise ValidationError("LLM base URL is invalid.")

    hostname = parsed.hostname
    if hostname is None:
        raise ValidationError("LLM base URL is invalid.")

    if provider is LLMProvider.GEMINI and hostname not in ALLOWED_GEMINI_HOSTS:
        raise ValidationError("Gemini base URL host is not allowed.")
    if provider is LLMProvider.GROQ and hostname not in ALLOWED_GROQ_HOSTS:
        raise ValidationError("Groq base URL host is not allowed.")

    return cleaned


def validate_llm_model(model: str) -> str:
    """Ensure the model name is a non-empty identifier."""
    cleaned = model.strip()
    if not cleaned:
        raise ValidationError("LLM model is required.")
    if len(cleaned) > 128:
        raise ValidationError("LLM model name is too long.")
    return cleaned
