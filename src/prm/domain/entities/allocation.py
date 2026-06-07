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

    def overlaps_period(self, date_from: date, date_to: date | None) -> bool:
        """True when this allocation's active range intersects [date_from, date_to]."""
        if self.status != AllocationStatus.ACTIVE:
            return False
        if date_to is not None and self.from_date > date_to:
            return False
        if self.to_date is not None and date_from > self.to_date:
            return False
        return True

    def overlaps(self, other: "Allocation") -> bool:
        """True when two active allocations share any calendar day."""
        if other.status != AllocationStatus.ACTIVE:
            return False
        return self.overlaps_period(other.from_date, other.to_date)
