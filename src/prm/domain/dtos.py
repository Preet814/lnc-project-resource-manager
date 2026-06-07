"""Data transfer objects returned across application boundaries."""

from dataclasses import dataclass
from datetime import UTC, datetime

from prm.domain.enums import (
    EmployeeWorkStatus,
    ProficiencyLevel,
    Role,
    SkillCategory,
    UserAccountStatus,
)


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


@dataclass(frozen=True, slots=True)
class EmployeeSummary:
    """Compact employee row for admin list screens (BRD §3.1.2)."""

    id: int
    full_name: str
    department: str
    work_status: EmployeeWorkStatus
    is_active: bool

    def is_on_bench(self) -> bool:
        return self.work_status == EmployeeWorkStatus.BENCH

    def is_allocated(self) -> bool:
        return self.work_status == EmployeeWorkStatus.ALLOCATED


@dataclass(frozen=True, slots=True)
class EmployeeListResult:
    """All employees plus bench/allocated counts for the admin dashboard."""

    employees: tuple[EmployeeSummary, ...]
    total: int
    allocated_count: int
    bench_count: int


@dataclass(frozen=True, slots=True)
class EmployeeSkillDetail:
    """Skill row for admin manage-skills screen (BRD §3.1.4)."""

    employee_skill_id: int
    skill_id: int
    skill_name: str
    category: SkillCategory
    proficiency: ProficiencyLevel
    assigned_at: datetime
