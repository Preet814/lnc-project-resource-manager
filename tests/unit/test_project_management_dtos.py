"""Unit tests for admin project-management DTOs."""

from datetime import datetime

from prm.domain.dtos import MilestoneDetail, ProjectListResult, ProjectSummary
from prm.domain.enums import MilestoneStatus, ProjectStatus


def test_project_list_result_stores_status_counts() -> None:
    projects = (
        ProjectSummary(
            201,
            "Alpha Portal",
            "Ankit Shah",
            datetime(2026, 6, 30).date(),
            ProjectStatus.ACTIVE,
        ),
        ProjectSummary(
            202,
            "Beta CRM",
            "Ankit Shah",
            datetime(2026, 8, 15).date(),
            ProjectStatus.ACTIVE,
        ),
        ProjectSummary(
            204,
            "Delta Migrate",
            "Rohan Verma",
            datetime(2026, 9, 30).date(),
            ProjectStatus.PLANNED,
        ),
    )
    result = ProjectListResult(
        projects=projects,
        total=3,
        active_count=2,
        planned_count=1,
        on_hold_count=0,
    )

    assert len(result.projects) == 3
    assert result.total == 3
    assert result.active_count == 2
    assert result.planned_count == 1
    assert result.on_hold_count == 0


def test_milestone_detail_fields() -> None:
    detail = MilestoneDetail(
        milestone_id=2,
        title="Backend API",
        due_date=datetime(2026, 4, 15).date(),
        status=MilestoneStatus.IN_PROGRESS,
        sequence_order=2,
    )

    assert detail.title == "Backend API"
    assert detail.status == MilestoneStatus.IN_PROGRESS
    assert detail.sequence_order == 2
