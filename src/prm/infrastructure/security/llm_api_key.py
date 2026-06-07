"""Encrypt and mask LLM API keys stored in system configuration."""

from base64 import urlsafe_b64encode
from hashlib import sha256

from cryptography.fernet import Fernet, InvalidToken

from prm.domain.constants import LLM_API_KEY_MASK
from prm.domain.exceptions import ValidationError


def _derive_fernet_key(secret_key: str) -> bytes:
    digest = sha256(secret_key.encode("utf-8")).digest()
    return urlsafe_b64encode(digest)


class FernetLlmApiKeyProtector:
    """Encrypt API keys at rest using a Fernet key derived from the app secret."""

    def __init__(self, secret_key: str) -> None:
        self._fernet = Fernet(_derive_fernet_key(secret_key))

    def encrypt(self, api_key: str) -> str:
        return self._fernet.encrypt(api_key.encode("utf-8")).decode("utf-8")

    def decrypt(self, encrypted: str) -> str:
        try:
            return self._fernet.decrypt(encrypted.encode("utf-8")).decode("utf-8")
        except InvalidToken as exc:
            raise ValidationError("Stored LLM API key could not be decrypted.") from exc

    @staticmethod
    def mask(encrypted: str | None) -> str | None:
        if not encrypted:
            return None
        return LLM_API_KEY_MASK
