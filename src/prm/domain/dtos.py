"""Data transfer objects returned across application boundaries."""

from dataclasses import dataclass
from datetime import UTC, datetime

from prm.domain.enums import Role


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
