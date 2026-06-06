"""Unit tests for auth-related domain types."""

from datetime import UTC, datetime, timedelta

from prm.domain.dtos import AuthToken
from prm.domain.entities.user import User
from prm.domain.enums import Role, UserAccountStatus
from tests.unit.credentials import TEST_EMAIL, TEST_FULL_NAME, TEST_USERNAME


def _sample_user(*, force_password_change: bool = True) -> User:
    now = datetime.now(UTC)
    return User(
        id=1,
        full_name=TEST_FULL_NAME,
        username=TEST_USERNAME,
        email=TEST_EMAIL,
        password_hash="hashed",
        role=Role.ADMIN,
        account_status=UserAccountStatus.ACTIVE,
        force_password_change=force_password_change,
        created_at=now,
        updated_at=now,
    )


def test_user_requires_password_change() -> None:
    assert _sample_user(force_password_change=True).requires_password_change()
    assert not _sample_user(force_password_change=False).requires_password_change()


def test_user_is_active() -> None:
    assert _sample_user().is_active()

    now = datetime.now(UTC)
    inactive = User(
        id=2,
        full_name="Inactive User",
        username="inactive",
        email="inactive@local",
        password_hash="hashed",
        role=Role.EMPLOYEE,
        account_status=UserAccountStatus.INACTIVE,
        force_password_change=False,
        created_at=now,
        updated_at=now,
    )
    assert not inactive.is_active()


def test_auth_token_is_valid_before_expiry() -> None:
    expires_at = datetime.now(UTC) + timedelta(hours=1)
    token = AuthToken(token="jwt", user_id=1, expires_at=expires_at)
    assert token.is_valid()


def test_auth_token_is_invalid_after_expiry() -> None:
    expires_at = datetime.now(UTC) - timedelta(minutes=1)
    token = AuthToken(token="jwt", user_id=1, expires_at=expires_at)
    assert not token.is_valid()
