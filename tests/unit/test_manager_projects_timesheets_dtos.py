"""Unit tests for manager project and team timesheet DTOs."""

from datetime import UTC, date, datetime

from prm.domain.dtos import (
    EngineerTimesheetEntryDetail,
    EngineerTimesheetWeekDetail,
    ManagerProjectDetail,
    ManagerProjectListResult,
    ManagerProjectMilestoneRow,
    ManagerProjectResourceRow,
    ManagerProjectSummary,
    TeamTimesheetListResult,
    TeamTimesheetRow,
)
from prm.domain.enums import (
    MilestoneStatus,
    ProjectHealthStatus,
    TimesheetWeekStatus,
)


def test_manager_project_list_result() -> None:
    projects = (
        ManagerProjectSummary(
            project_id=1,
            name="Alpha Portal",
            end_date=date(2026, 6, 30),
            health_status=ProjectHealthStatus.AT_RISK,
        ),
        ManagerProjectSummary(
            project_id=2,
            name="Beta CRM",
            end_date=date(2026, 8, 15),
            health_status=ProjectHealthStatus.ON_TRACK,
        ),
    )
    result = ManagerProjectListResult(projects=projects, total=2)

    assert result.total == 2
    assert result.projects[0].health_status == ProjectHealthStatus.AT_RISK


def test_manager_project_detail_fields() -> None:
    detail = ManagerProjectDetail(
        project_id=1,
        name="Alpha Portal",
        health_status=ProjectHealthStatus.AT_RISK,
        health_computed_at=datetime(2026, 5, 12, 10, 0, tzinfo=UTC),
        risk_flags=(
            "Backend API milestone is 5 days overdue",
            "Ravi Kumar logged only 4 hrs last week (expected 20 hrs)",
        ),
        milestones=(
            ManagerProjectMilestoneRow(
                milestone_id=2,
                title="Backend API",
                due_date=date(2026, 4, 15),
                status=MilestoneStatus.IN_PROGRESS,
                sequence_order=2,
                is_overdue=True,
            ),
        ),
        allocated_resources=(
            ManagerProjectResourceRow(
                user_id=10,
                user_full_name="Ravi Kumar",
                utilisation_percent=50,
                from_date=date(2026, 3, 1),
                to_date=date(2026, 6, 30),
            ),
        ),
    )

    assert detail.risk_flags[0].startswith("Backend API")
    assert detail.milestones[0].is_overdue is True
    assert detail.allocated_resources[0].user_full_name == "Ravi Kumar"


def test_team_timesheet_list_result_includes_missed() -> None:
    rows = (
        TeamTimesheetRow(
            user_id=10,
            user_full_name="Ravi Kumar",
            project_id=1,
            project_name="Alpha Portal",
            hours=18,
            status=TimesheetWeekStatus.SUBMITTED,
        ),
        TeamTimesheetRow(
            user_id=12,
            user_full_name="Anil Mehta",
            project_id=3,
            project_name="Gamma Rewrite",
            hours=0,
            status=TimesheetWeekStatus.MISSED,
        ),
    )
    result = TeamTimesheetListResult(
        week_start_date=date(2026, 5, 12),
        rows=rows,
        total=2,
    )

    assert result.week_start_date == date(2026, 5, 12)
    assert result.rows[1].status == TimesheetWeekStatus.MISSED
    assert result.rows[1].hours == 0


def test_employee_timesheet_week_detail_fields() -> None:
    detail = EngineerTimesheetWeekDetail(
        user_id=10,
        user_full_name="Ravi Kumar",
        week_start_date=date(2026, 5, 12),
        status=TimesheetWeekStatus.SUBMITTED,
        total_hours=38,
        entries=(
            EngineerTimesheetEntryDetail(
                project_id=1,
                project_name="Alpha Portal",
                hours_worked=18,
                activity_tags=("Backend Api", "Microservices"),
            ),
            EngineerTimesheetEntryDetail(
                project_id=2,
                project_name="Beta CRM",
                hours_worked=20,
                activity_tags=("Frontend",),
            ),
        ),
    )

    assert detail.total_hours == 38
    assert len(detail.entries) == 2
    assert detail.entries[0].activity_tags == ("Backend Api", "Microservices")
