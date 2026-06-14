"""User domain entity."""

from dataclasses import dataclass
from datetime import datetime

from prm.domain.enums import ResourceWorkStatus, Role, UserAccountStatus


@dataclass(frozen=True, slots=True)
class User:
    """Person account — unified admin, manager, or engineer."""

    id: int
    full_name: str
    username: str
    email: str
    password_hash: str
    role_id: int
    role: Role
    department_id: int | None
    designation_id: int | None
    manager_id: int | None
    account_status: UserAccountStatus
    force_password_change: bool
    email_verified: bool
    created_at: datetime
    updated_at: datetime
    department_name: str | None = None
    designation_name: str | None = None
    work_status: ResourceWorkStatus | None = None
    utilisation_percent: int | None = None

    def requires_password_change(self) -> bool:
        return self.force_password_change

    def requires_email_verification(self) -> bool:
        return not self.email_verified

    def is_active(self) -> bool:
        return self.account_status == UserAccountStatus.ACTIVE

    def is_engineer(self) -> bool:
        return self.role == Role.ENGINEER

    def is_on_bench(self) -> bool:
        return self.work_status == ResourceWorkStatus.BENCH
