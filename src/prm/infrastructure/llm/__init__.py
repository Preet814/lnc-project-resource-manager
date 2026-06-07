"""LLM provider adapters (Strategy + Factory — DESIGN.md)."""

from prm.infrastructure.llm.factory import create_llm_client, create_llm_client_from_settings
from prm.infrastructure.llm.fake_client import FakeLlmClient

__all__ = ["FakeLlmClient", "create_llm_client", "create_llm_client_from_settings"]
