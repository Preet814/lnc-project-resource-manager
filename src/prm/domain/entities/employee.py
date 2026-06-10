"""Employee domain entity."""

from dataclasses import dataclass
from datetime import datetime

from prm.domain.constants import MAX_UTILISATION_PERCENT
from prm.domain.enums import EmployeeWorkStatus


@dataclass(frozen=True, slots=True)
class Employee:
    """Work profile linked to a user account (class diagram «entity»)."""

    id: int
    user_id: int | None
    manager_id: int | None
    full_name: str
    email: str
    department: str
    designation: str
    work_status: EmployeeWorkStatus
    is_active: bool
    current_utilisation_percent: int
    created_at: datetime

    def is_on_bench(self) -> bool:
        return self.work_status == EmployeeWorkStatus.BENCH

    def is_over_utilised(self) -> bool:
        return self.current_utilisation_percent > MAX_UTILISATION_PERCENT
