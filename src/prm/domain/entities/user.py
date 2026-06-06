"""User domain entity."""

from dataclasses import dataclass
from datetime import datetime

from prm.domain.enums import Role, UserAccountStatus


@dataclass(frozen=True, slots=True)
class User:
    """Login account — mirrors class diagram User entity."""

    id: int
    full_name: str
    username: str
    email: str
    password_hash: str
    role: Role
    account_status: UserAccountStatus
    force_password_change: bool
    created_at: datetime
    updated_at: datetime

    def requires_password_change(self) -> bool:
        return self.force_password_change

    def is_active(self) -> bool:
        return self.account_status == UserAccountStatus.ACTIVE
