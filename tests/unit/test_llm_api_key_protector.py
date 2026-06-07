"""Unit tests for FernetLlmApiKeyProtector."""

import pytest

from prm.domain.constants import LLM_API_KEY_MASK
from prm.domain.exceptions import ValidationError
from prm.infrastructure.security.llm_api_key import FernetLlmApiKeyProtector


def test_encrypt_and_decrypt_round_trip() -> None:
    protector = FernetLlmApiKeyProtector("test-secret-key")

    encrypted = protector.encrypt("provider-api-key")
    decrypted = protector.decrypt(encrypted)

    assert encrypted != "provider-api-key"
    assert decrypted == "provider-api-key"


def test_mask_returns_none_when_key_missing() -> None:
    assert FernetLlmApiKeyProtector.mask(None) is None
    assert FernetLlmApiKeyProtector.mask("") is None


def test_mask_hides_stored_value() -> None:
    assert FernetLlmApiKeyProtector.mask("encrypted-value") == LLM_API_KEY_MASK


def test_decrypt_rejects_invalid_token() -> None:
    protector = FernetLlmApiKeyProtector("test-secret-key")

    with pytest.raises(ValidationError, match="Stored LLM API key could not be decrypted"):
        protector.decrypt("not-a-valid-token")
