"""Unit tests for JWT token service."""

from datetime import UTC, datetime, timedelta

import pytest
from jose import jwt

from prm.domain.enums import Role
from prm.domain.exceptions import AuthenticationError
from prm.infrastructure.security.jwt import JWT_ALGORITHM, JwtTokenService
from tests.unit.credentials import TEST_USERNAME

SECRET = "test-secret-key-for-unit-tests"
SERVICE = JwtTokenService(secret_key=SECRET, expire_minutes=60)


def test_create_and_decode_access_token_roundtrip() -> None:
    auth_token = SERVICE.create_access_token(
        user_id=1,
        username=TEST_USERNAME,
        role=Role.ADMIN,
        force_password_change=True,
    )

    assert auth_token.token
    assert auth_token.user_id == 1
    assert auth_token.is_valid()

    payload = SERVICE.decode_access_token(auth_token.token)
    assert payload.user_id == 1
    assert payload.username == TEST_USERNAME
    assert payload.role == Role.ADMIN
    assert payload.force_password_change is True


def test_decode_expired_token_raises_authentication_error() -> None:
    expired_at = datetime.now(UTC) - timedelta(minutes=1)
    claims = {
        "sub": "1",
        "username": TEST_USERNAME,
        "role": Role.ADMIN.value,
        "force_password_change": False,
        "exp": expired_at,
    }
    token = jwt.encode(claims, SECRET, algorithm=JWT_ALGORITHM)

    with pytest.raises(AuthenticationError, match="Invalid or expired"):
        SERVICE.decode_access_token(token)


def test_decode_invalid_token_raises_authentication_error() -> None:
    with pytest.raises(AuthenticationError, match="Invalid or expired"):
        SERVICE.decode_access_token("not-a-valid-jwt")
