"""Data transfer objects returned across application boundaries."""

from dataclasses import dataclass
from datetime import UTC, datetime

from prm.domain.enums import Role, UserAccountStatus


@dataclass(frozen=True, slots=True)
class AuthToken:
    """Login outcome — JWT access token and metadata (class diagram «DTO»)."""

    token: str
    user_id: int
    expires_at: datetime

    def is_valid(self, now: datetime | None = None) -> bool:
        reference = now or datetime.now(UTC)
        expires = self.expires_at
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=UTC)
        if reference.tzinfo is None:
            reference = reference.replace(tzinfo=UTC)
        return reference < expires


@dataclass(frozen=True, slots=True)
class LoginResult:
    """Successful login — token plus flags the console needs for routing."""

    access_token: str
    token_type: str
    user_id: int
    username: str
    full_name: str
    role: Role
    force_password_change: bool
    expires_at: datetime


@dataclass(frozen=True, slots=True)
class UserSummary:
    """Compact user row for admin list screens (BRD §3.4.2)."""

    id: int
    username: str
    full_name: str
    role: Role
    account_status: UserAccountStatus

    def is_active(self) -> bool:
        return self.account_status == UserAccountStatus.ACTIVE


@dataclass(frozen=True, slots=True)
class UserListResult:
    """All users plus aggregate counts for the admin dashboard."""

    users: tuple[UserSummary, ...]
    total: int
    active_count: int
    inactive_count: int
