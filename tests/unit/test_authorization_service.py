"""Unit tests for AuthorizationService."""

import pytest

from prm.application.authorization_service import AuthorizationService
from prm.domain.entities.user import User
from prm.domain.enums import Role, UserAccountStatus
from prm.domain.exceptions import UnauthorizedError


def _user(*, role: Role = Role.ADMIN, active: bool = True) -> User:
    from datetime import UTC, datetime

    now = datetime.now(UTC)
    return User(
        id=1,
        full_name="Test User",
        username="testuser",
        email="test@local",
        password_hash="hash",
        role=role,
        account_status=UserAccountStatus.ACTIVE if active else UserAccountStatus.INACTIVE,
        force_password_change=False,
        created_at=now,
        updated_at=now,
    )


def test_assert_active_passes_for_active_user() -> None:
    AuthorizationService().assert_active(_user())


def test_assert_active_raises_for_inactive_user() -> None:
    with pytest.raises(UnauthorizedError, match="inactive"):
        AuthorizationService().assert_active(_user(active=False))


def test_assert_role_passes_when_role_allowed() -> None:
    AuthorizationService().assert_role(_user(role=Role.MANAGER), Role.MANAGER, Role.ADMIN)


def test_assert_role_raises_when_role_not_allowed() -> None:
    with pytest.raises(UnauthorizedError, match="not permitted"):
        AuthorizationService().assert_role(_user(role=Role.EMPLOYEE), Role.ADMIN)
