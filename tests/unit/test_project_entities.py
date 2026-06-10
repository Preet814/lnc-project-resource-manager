"""Unit tests for project and milestone domain entities."""

from datetime import datetime

from prm.domain.entities.milestone import Milestone
from prm.domain.entities.project import Project
from prm.domain.enums import MilestoneStatus, ProjectHealthStatus, ProjectStatus


def _project(*, status: ProjectStatus, manager_user_id: int = 2) -> Project:
    return Project(
        id=201,
        name="Alpha Portal",
        description="Customer portal rewrite",
        start_date=datetime(2026, 3, 1).date(),
        end_date=datetime(2026, 6, 30).date(),
        status=status,
        manager_user_id=manager_user_id,
        total_story_points=120,
        health_status=ProjectHealthStatus.ON_TRACK,
        health_computed_at=None,
    )


def test_project_is_owned_by() -> None:
    project = _project(status=ProjectStatus.ACTIVE, manager_user_id=5)

    assert project.is_owned_by(5) is True
    assert project.is_owned_by(3) is False


def test_project_allows_allocation() -> None:
    assert _project(status=ProjectStatus.PLANNED).allows_allocation() is True
    assert _project(status=ProjectStatus.ACTIVE).allows_allocation() is True
    assert _project(status=ProjectStatus.ON_HOLD).allows_allocation() is False
    assert _project(status=ProjectStatus.COMPLETED).allows_allocation() is False


def test_milestone_is_overdue() -> None:
    milestone = Milestone(
        id=1,
        project_id=201,
        title="Backend API",
        due_date=datetime(2026, 4, 15).date(),
        status=MilestoneStatus.IN_PROGRESS,
        sequence_order=2,
        story_points=40,
    )
    done = Milestone(
        id=2,
        project_id=201,
        title="Design Complete",
        due_date=datetime(2026, 4, 1).date(),
        status=MilestoneStatus.DONE,
        sequence_order=1,
        story_points=20,
    )

    assert milestone.is_overdue(datetime(2026, 4, 20).date()) is True
    assert milestone.is_overdue(datetime(2026, 4, 10).date()) is False
    assert done.is_overdue(datetime(2026, 4, 20).date()) is False
