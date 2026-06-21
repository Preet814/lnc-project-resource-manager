"""Shared rules for timesheet weeks, allocations, and submission freeze."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

from prm.domain.constants import TIMESHEET_FREEZE_HOUR, TIMESHEET_FREEZE_MINUTE
from prm.domain.entities.allocation import Allocation
from prm.domain.enums import TimesheetWeekStatus
from prm.domain.week_calendar import last_completed_week_start, week_end


def allocation_covers_week(
    allocation: Allocation,
    week_start: date,
    period_end: date,
) -> bool:
    if allocation.from_date > period_end:
        return False
    if allocation.to_date is not None and week_start > allocation.to_date:
        return False
    return True


def engineer_has_allocation_for_week(
    allocations: tuple[Allocation, ...] | list[Allocation],
    week_start: date,
) -> bool:
    period_end = week_end(week_start)
    return any(
        allocation_covers_week(allocation, week_start, period_end)
        for allocation in allocations
    )


def is_timesheet_complete(week) -> bool:
    if week is None:
        return False
    return week.status in (TimesheetWeekStatus.SUBMITTED, TimesheetWeekStatus.MISSED)


def freeze_datetime_for_completed_week(week_start: date, tz: ZoneInfo) -> datetime:
    """Tuesday 17:30 in ``tz`` during the week after the completed Monday week."""
    freeze_day = week_start + timedelta(days=8)
    return datetime(
        freeze_day.year,
        freeze_day.month,
        freeze_day.day,
        TIMESHEET_FREEZE_HOUR,
        TIMESHEET_FREEZE_MINUTE,
        tzinfo=tz,
    )


def is_last_completed_week_frozen(
    week_start: date,
    *,
    now: datetime,
    app_timezone: str,
    enabled: bool,
) -> bool:
    if not enabled:
        return False
    last_week = last_completed_week_start(now.date())
    if last_week is None or week_start != last_week:
        return False
    tz = ZoneInfo(app_timezone)
    reference = now if now.tzinfo is not None else now.replace(tzinfo=UTC)
    freeze_at = freeze_datetime_for_completed_week(last_week, tz)
    return reference.astimezone(tz) >= freeze_at
