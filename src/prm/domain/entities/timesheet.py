"""Timesheet domain entities."""

from dataclasses import dataclass
from datetime import date, datetime

from prm.domain.enums import ActivityTag, TimesheetWeekStatus


@dataclass(frozen=True, slots=True)
class TimesheetWeek:
    """Weekly timesheet aggregate for an employee."""

    id: int
    employee_id: int
    week_start_date: date
    status: TimesheetWeekStatus
    total_hours: int
    submitted_at: datetime | None


@dataclass(frozen=True, slots=True)
class TimesheetEntry:
    """Project line within a timesheet week."""

    id: int
    timesheet_week_id: int
    project_id: int
    hours_worked: int
    activity_tags: tuple[ActivityTag, ...]
