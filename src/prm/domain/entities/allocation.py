"""Allocation domain entity."""

from dataclasses import dataclass
from datetime import date

from prm.domain.enums import AllocationStatus


@dataclass(frozen=True, slots=True)
class Allocation:
    """Employee allocation to a project for a date range."""

    id: int
    employee_id: int
    project_id: int
    utilisation_percent: int
    from_date: date
    to_date: date | None
    status: AllocationStatus
    created_by_user_id: int

    def is_active_on(self, as_of: date) -> bool:
        if self.status != AllocationStatus.ACTIVE:
            return False
        if as_of < self.from_date:
            return False
        return not (self.to_date is not None and as_of > self.to_date)
