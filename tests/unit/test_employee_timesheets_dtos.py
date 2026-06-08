"""Unit tests for employee timesheet and allocation DTOs."""

from datetime import UTC, date, datetime

from prm.domain.dtos import (
    MyAllocationRow,
    MyAllocationsResult,
    MyTimesheetEntryDetail,
    MyTimesheetListResult,
    MyTimesheetWeekDetail,
    MyTimesheetWeekSummary,
    SubmittedTimesheetResult,
    SubmitTimesheetCommand,
    SubmitTimesheetEntry,
    WeekAllocationRow,
    WeekAllocationsResult,
)
from prm.domain.enums import ActivityTag, AllocationStatus, TimesheetWeekStatus


def test_submit_timesheet_command() -> None:
    command = SubmitTimesheetCommand(
        week_start_date=date(2026, 5, 12),
        entries=(
            SubmitTimesheetEntry(
                project_id=1,
                hours_worked=18,
                activity_tags=(ActivityTag.MICROSERVICES, ActivityTag.WEBSOCKET),
            ),
            SubmitTimesheetEntry(
                project_id=2,
                hours_worked=20,
                activity_tags=(ActivityTag.BACKEND_API, ActivityTag.BUG_FIXING),
            ),
        ),
    )

    assert command.week_start_date == date(2026, 5, 12)
    assert len(command.entries) == 2
    assert command.entries[0].activity_tags[0] == ActivityTag.MICROSERVICES


def test_submitted_timesheet_result() -> None:
    result = SubmittedTimesheetResult(
        week_start_date=date(2026, 5, 12),
        status=TimesheetWeekStatus.SUBMITTED,
        total_hours=38,
        submitted_at=datetime(2026, 5, 16, 9, 30, tzinfo=UTC),
    )

    assert result.status == TimesheetWeekStatus.SUBMITTED
    assert result.total_hours == 38


def test_week_allocations_result() -> None:
    result = WeekAllocationsResult(
        week_start_date=date(2026, 5, 12),
        max_weekly_hours=40,
        allocations=(
            WeekAllocationRow(
                project_id=1,
                project_name="Alpha Portal",
                utilisation_percent=50,
                expected_max_hours=20,
            ),
            WeekAllocationRow(
                project_id=2,
                project_name="Beta CRM",
                utilisation_percent=50,
                expected_max_hours=20,
            ),
        ),
    )

    assert result.max_weekly_hours == 40
    assert result.allocations[0].expected_max_hours == 20
    assert result.allocations[1].project_name == "Beta CRM"


def test_my_allocations_result() -> None:
    result = MyAllocationsResult(
        allocations=(
            MyAllocationRow(
                project_id=1,
                project_name="Alpha Portal",
                utilisation_percent=50,
                from_date=date(2026, 3, 1),
                to_date=date(2026, 6, 30),
                status=AllocationStatus.ACTIVE,
            ),
            MyAllocationRow(
                project_id=2,
                project_name="Beta CRM",
                utilisation_percent=50,
                from_date=date(2026, 4, 1),
                to_date=date(2026, 7, 31),
                status=AllocationStatus.ACTIVE,
            ),
        ),
        total_utilisation_percent=100,
    )

    assert result.total_utilisation_percent == 100
    assert result.allocations[0].status == AllocationStatus.ACTIVE


def test_my_timesheet_list_result() -> None:
    weeks = (
        MyTimesheetWeekSummary(
            week_start_date=date(2026, 5, 12),
            total_hours=38,
            status=TimesheetWeekStatus.SUBMITTED,
        ),
        MyTimesheetWeekSummary(
            week_start_date=date(2026, 4, 21),
            total_hours=0,
            status=TimesheetWeekStatus.MISSED,
        ),
    )
    result = MyTimesheetListResult(weeks=weeks, total=2)

    assert result.total == 2
    assert result.weeks[1].status == TimesheetWeekStatus.MISSED


def test_my_timesheet_week_detail() -> None:
    detail = MyTimesheetWeekDetail(
        week_start_date=date(2026, 5, 5),
        status=TimesheetWeekStatus.SUBMITTED,
        total_hours=40,
        entries=(
            MyTimesheetEntryDetail(
                project_id=1,
                project_name="Alpha Portal",
                hours_worked=20,
                activity_tags=("Microservices", "WebSocket"),
            ),
            MyTimesheetEntryDetail(
                project_id=2,
                project_name="Beta CRM",
                hours_worked=20,
                activity_tags=("Backend Api", "Bug Fixing"),
            ),
        ),
    )

    assert detail.total_hours == 40
    assert len(detail.entries) == 2
    assert detail.entries[0].activity_tags == ("Microservices", "WebSocket")
