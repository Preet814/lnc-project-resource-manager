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
