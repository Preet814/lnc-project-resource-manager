"""Allocation domain entity."""

from dataclasses import dataclass
from datetime import date

from prm.domain.enums import AllocationStatus
from prm.domain.week_calendar import prorated_hours_for_overlap, week_end


@dataclass(frozen=True, slots=True)
class Allocation:
    """User allocation to a project for a date range."""

    id: int
    user_id: int
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

    def overlap_days_in_period(self, period_start: date, period_end: date) -> int:
        """Count calendar days this allocation intersects [period_start, period_end]."""
        if not self.overlaps_period(period_start, period_end):
            return 0
        overlap_start = max(self.from_date, period_start)
        if self.to_date is not None:
            overlap_end = min(self.to_date, period_end)
        else:
            overlap_end = period_end
        return (overlap_end - overlap_start).days + 1

    def expected_hours_for_week(self, week_start: date, *, max_weekly_hours: int) -> int:
        """Expected hours for a Monday week, prorated when allocation is partial."""
        period_end = week_end(week_start)
        overlap_days = self.overlap_days_in_period(week_start, period_end)
        full_week_hours = (self.utilisation_percent * max_weekly_hours) // 100
        return prorated_hours_for_overlap(full_week_hours, overlap_days)
