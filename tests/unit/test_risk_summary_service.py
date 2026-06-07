"""Unit tests for RiskSummaryService."""

from datetime import UTC, date, datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from prm.application.authorization_service import AuthorizationService
from prm.application.risk_summary_service import RiskSummaryService
from prm.domain.constants import AI_RISK_SUMMARY_DISCLAIMER
from prm.domain.entities.project_health_snapshot import ProjectHealthSnapshot
from prm.domain.entities.timesheet import TimesheetEntry, TimesheetWeek
from prm.domain.enums import (
    MilestoneStatus,
    ProjectHealthStatus,
    ProjectStatus,
    Role,
    TimesheetWeekStatus,
)
from prm.domain.exceptions import UnauthorizedError
from prm.infrastructure.db.models import (
    AllocationModel,
    EmployeeModel,
    MilestoneModel,
    ProjectModel,
    UserModel,
)
from prm.infrastructure.db.repositories import (
    SqlAlchemyAllocationRepository,
    SqlAlchemyEmployeeRepository,
    SqlAlchemyMilestoneRepository,
    SqlAlchemyProjectRepository,
    SqlAlchemyUserRepository,
)
from prm.infrastructure.llm.fake_client import FakeLlmClient
from prm.infrastructure.security.password import BcryptPasswordHasher


class _FakeHealthSnapshotRepository:
    def __init__(self, snapshot: ProjectHealthSnapshot | None = None) -> None:
        self._snapshot = snapshot

    def find_latest_for_project(self, project_id: int) -> ProjectHealthSnapshot | None:
        _ = project_id
        return self._snapshot


class _FakeTimesheetRepository:
    def __init__(
        self,
        *,
        week: TimesheetWeek | None = None,
        entries: list[TimesheetEntry] | None = None,
    ) -> None:
        self._week = week
        self._entries = entries or []

    def list_recent_activity_tags(
        self,
        employee_id: int,
        *,
        weeks: int = 4,
        as_of: date | None = None,
    ) -> list[str]:
        _ = employee_id, weeks, as_of
        return []

    def find_week_by_employee(
        self,
        employee_id: int,
        week_start_date: date,
    ) -> TimesheetWeek | None:
        _ = employee_id, week_start_date
        return self._week

    def list_entries_for_week(self, timesheet_week_id: int) -> list[TimesheetEntry]:
        _ = timesheet_week_id
        return list(self._entries)


def _session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    UserModel.__table__.create(engine, checkfirst=True)
    EmployeeModel.__table__.create(engine, checkfirst=True)
    ProjectModel.__table__.create(engine, checkfirst=True)
    MilestoneModel.__table__.create(engine, checkfirst=True)
    AllocationModel.__table__.create(engine, checkfirst=True)
    return Session(engine)


def _service(
    session: Session,
    *,
    llm: FakeLlmClient,
    snapshot: ProjectHealthSnapshot | None = None,
    timesheets: _FakeTimesheetRepository | None = None,
    max_weekly_hours: int = 40,
) -> RiskSummaryService:
    project_repo = SqlAlchemyProjectRepository(session)
    return RiskSummaryService(
        project_repository=project_repo,
        milestone_repository=SqlAlchemyMilestoneRepository(session),
        allocation_repository=SqlAlchemyAllocationRepository(session),
        employee_repository=SqlAlchemyEmployeeRepository(session),
        health_snapshot_repository=_FakeHealthSnapshotRepository(snapshot),
        timesheet_repository=timesheets or _FakeTimesheetRepository(),
        authorization=AuthorizationService(project_repo),
        llm_client=llm,
        max_weekly_hours=max_weekly_hours,
    )


def _seed_manager_project(
    session: Session,
    *,
    health_status: ProjectHealthStatus = ProjectHealthStatus.AT_RISK,
) -> tuple[int, int]:
    user_repo = SqlAlchemyUserRepository(session)
    hasher = BcryptPasswordHasher()
    manager = user_repo.create(
        full_name="Ankit Shah",
        username="ankit",
        email="ankit@example.test",
        password_hash=hasher.hash("TempPass1"),
        role=Role.MANAGER,
    )
    project_repo = SqlAlchemyProjectRepository(session)
    project = project_repo.create(
        name="Alpha Portal",
        description="Customer portal rewrite",
        start_date=date(2026, 3, 1),
        end_date=date(2026, 6, 30),
        status=ProjectStatus.ACTIVE,
        manager_user_id=manager.id,
    )
    project_model = session.get(ProjectModel, project.id)
    assert project_model is not None
    project_model.health_status = health_status
    project_model.health_computed_at = datetime(2026, 5, 12, 10, 0, tzinfo=UTC)
    session.flush()
    return manager.id, project.id


def test_summarize_risk_returns_llm_summary_with_project_context() -> None:
    session = _session()
    manager_id, project_id = _seed_manager_project(session)
    user_repo = SqlAlchemyUserRepository(session)
    hasher = BcryptPasswordHasher()
    employee_user = user_repo.create(
        full_name="Employee User",
        username="employee",
        email="employee@example.test",
        password_hash=hasher.hash("TempPass1"),
        role=Role.EMPLOYEE,
    )
    employee = SqlAlchemyEmployeeRepository(session).create(
        user_id=employee_user.id,
        full_name="Ravi Kumar",
        email="employee@example.test",
        department="Backend",
        designation="Developer",
    )
    milestone_repo = SqlAlchemyMilestoneRepository(session)
    milestone_repo.create(
        project_id=project_id,
        title="Backend API",
        due_date=date(2026, 4, 15),
        status=MilestoneStatus.IN_PROGRESS,
        sequence_order=2,
    )
    session.add(
        AllocationModel(
            employee_id=employee.id,
            project_id=project_id,
            utilisation_percent=50,
            from_date=date(2026, 3, 1),
            to_date=date(2026, 6, 30),
            created_by_user_id=manager_id,
        )
    )
    session.commit()
    snapshot = ProjectHealthSnapshot(
        id=1,
        project_id=project_id,
        status=ProjectHealthStatus.AT_RISK,
        risk_flags=("Backend API milestone is 5 days overdue",),
        computed_at=datetime(2026, 5, 12, 10, 0, tzinfo=UTC),
    )
    week = TimesheetWeek(
        id=1,
        employee_id=employee.id,
        week_start_date=date(2026, 5, 5),
        status=TimesheetWeekStatus.SUBMITTED,
        total_hours=4,
        submitted_at=datetime(2026, 5, 11, 12, 0, tzinfo=UTC),
    )
    entries = [
        TimesheetEntry(
            id=1,
            timesheet_week_id=1,
            project_id=project_id,
            hours_worked=4,
            activity_tags=(),
        )
    ]
    llm = FakeLlmClient(
        risk_summary="The Backend API milestone is overdue and hours logged are low.",
    )
    service = _service(
        session,
        llm=llm,
        snapshot=snapshot,
        timesheets=_FakeTimesheetRepository(week=week, entries=entries),
    )

    result = service.summarize_risk(
        manager_id,
        project_id,
        as_of=date(2026, 5, 12),
    )

    assert result.project_id == project_id
    assert "overdue" in result.summary.lower()
    assert result.disclaimer == AI_RISK_SUMMARY_DISCLAIMER
    assert len(llm.risk_calls) == 1
    context = llm.risk_calls[0]
    assert context.project_name == "Alpha Portal"
    assert context.risk_flags[0].startswith("Backend API")
    assert context.milestones[0].title == "Backend API"
    assert context.allocated_resources[0].employee_full_name == "Ravi Kumar"
    assert any(
        fact.hours_logged == 4 and fact.expected_hours == 20
        for fact in context.recent_timesheets
    )


def test_summarize_risk_requires_project_owner() -> None:
    session = _session()
    manager_id, project_id = _seed_manager_project(session)
    user_repo = SqlAlchemyUserRepository(session)
    hasher = BcryptPasswordHasher()
    other_manager = user_repo.create(
        full_name="Other Manager",
        username="other.manager",
        email="other@example.test",
        password_hash=hasher.hash("TempPass1"),
        role=Role.MANAGER,
    )
    project_repo = SqlAlchemyProjectRepository(session)
    other_project = project_repo.create(
        name="Beta CRM",
        description="CRM rollout",
        start_date=date(2026, 4, 1),
        end_date=date(2026, 8, 15),
        status=ProjectStatus.ACTIVE,
        manager_user_id=other_manager.id,
    )
    session.commit()
    llm = FakeLlmClient()

    with pytest.raises(UnauthorizedError, match="project owner"):
        _service(session, llm=llm).summarize_risk(manager_id, other_project.id)
