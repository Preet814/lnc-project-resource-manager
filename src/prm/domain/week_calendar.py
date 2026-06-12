"""Week boundaries for timesheet workflows (Monday-based weeks)."""

from datetime import date, timedelta

from prm.domain.exceptions import ValidationError


def week_start_on_or_before(reference: date) -> date:
    """Monday on or before the given date."""
    return reference - timedelta(days=reference.weekday())


def week_end(week_start: date) -> date:
    """Sunday ending the week that starts on week_start (must be Monday)."""
    return week_start + timedelta(days=6)


def assert_monday_week_start(week_start: date) -> None:
    """Reject week_start values that are not Monday."""
    if week_start.weekday() != 0:
        raise ValidationError("Week start date must be a Monday.")


def last_completed_week_start(reference: date) -> date | None:
    """Monday of the most recent fully elapsed week, or None if unavailable."""
    current_week_start = week_start_on_or_before(reference)
    if week_end(current_week_start) < reference:
        return current_week_start
    if current_week_start <= date(1970, 1, 5):
        return None
    return current_week_start - timedelta(weeks=1)


def prorated_hours_for_overlap(
    full_period_hours: int,
    overlap_days: int,
    *,
    period_days: int = 7,
) -> int:
    """Scale hours linearly when an allocation covers only part of a period."""
    if overlap_days <= 0:
        return 0
    return (full_period_hours * overlap_days) // period_days
