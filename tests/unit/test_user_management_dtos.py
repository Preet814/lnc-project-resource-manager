"""Unit tests for admin user-management DTOs."""

from prm.domain.dtos import UserListResult, UserSummary
from prm.domain.enums import Role, UserAccountStatus


def test_user_summary_is_active() -> None:
    active = UserSummary(
        id=1,
        username="alice",
        full_name="Alice",
        role=Role.ENGINEER,
        account_status=UserAccountStatus.ACTIVE,
    )
    inactive = UserSummary(
        id=2,
        username="bob",
        full_name="Bob",
        role=Role.MANAGER,
        account_status=UserAccountStatus.INACTIVE,
    )

    assert active.is_active() is True
    assert inactive.is_active() is False


def test_user_list_result_stores_counts() -> None:
    users = (
        UserSummary(1, "admin", "Admin", Role.ADMIN, UserAccountStatus.ACTIVE),
        UserSummary(2, "mgr", "Manager", Role.MANAGER, UserAccountStatus.INACTIVE),
    )
    result = UserListResult(users=users, total=2, active_count=1, inactive_count=1)

    assert len(result.users) == 2
    assert result.total == 2
    assert result.active_count == 1
    assert result.inactive_count == 1
