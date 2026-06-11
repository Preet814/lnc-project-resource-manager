"""Unit tests for TeamTimesheetService."""

from datetime import date

import pytest
from sqlalchemy import JSON
from sqlalchemy.orm import Session

from prm.application.team_timesheet_service import TeamTimesheetService
from prm.domain.enums import ActivityTag, Role, TimesheetWeekStatus
from prm.domain.exceptions import NotFoundError, UnauthorizedError
from prm.infrastructure.db.models import AllocationModel, ProjectModel, TimesheetEntryModel, TimesheetWeekModel
from prm.infrastructure.db.repositories import (
    SqlAlchemyAllocationRepository,
    SqlAlchemyProjectRepository,
    SqlAlchemyTimesheetRepository,
    SqlAlchemyUserRepository,
)
from tests.unit.engineer_fixtures import (
    create_allocation_tables,
    create_memory_session,
    create_timesheet_tables,
    create_user,
    seed_rbac,
)


def _session() -> Session:
    session = create_memory_session(include_project=True)
    create_allocation_tables(session)
    create_timesheet_tables(session)
    TimesheetEntryModel.__table__.c.activity_tags.type = JSON()
    return session


def _service(session: Session) -> TeamTimesheetService:
    return TeamTimesheetService(
        allocation_repository=SqlAlchemyAllocationRepository(session),
        user_repository=SqlAlchemyUserRepository(session),
        project_repository=SqlAlchemyProjectRepository(session),
        timesheet_repository=SqlAlchemyTimesheetRepository(session),
    )


def _seed_team(
    session: Session,
) -> tuple[int, int, int, int, int]:
    seed_rbac(session)
    manager_id = create_user(
        session,
        full_name="Ankit Shah",
        username="ankit",
        email="ankit@example.test",
        role=Role.MANAGER,
    )
    ravi_id = create_user(
        session,
        full_name="Ravi Kumar",
        username="employee",
        email="employee@example.test",
        role=Role.ENGINEER,
        manager_id=manager_id,
    )
    anil_id = create_user(
        session,
        full_name="Anil Mehta",
        username="missed",
        email="missed@example.test",
        role=Role.ENGINEER,
        manager_id=manager_id,
    )
    alpha = ProjectModel(
        name="Alpha Portal",
        description="Alpha",
        start_date=date(2026, 1, 1),
        manager_user_id=manager_id,
    )
    gamma = ProjectModel(
        name="Gamma Rewrite",
        description="Gamma",
        start_date=date(2026, 1, 1),
        manager_user_id=manager_id,
    )
    session.add_all([alpha, gamma])
    session.flush()
    session.add_all(
        [
            AllocationModel(
                user_id=ravi_id,
                project_id=alpha.id,
                utilisation_percent=50,
                from_date=date(2026, 3, 1),
                to_date=date(2026, 6, 30),
                created_by_user_id=manager_id,
            ),
            AllocationModel(
                user_id=anil_id,
                project_id=gamma.id,
                utilisation_percent=100,
                from_date=date(2026, 3, 1),
                to_date=date(2026, 7, 1),
                created_by_user_id=manager_id,
            ),
        ]
    )
    session.flush()
    return manager_id, ravi_id, anil_id, alpha.id, gamma.id


def test_list_team_timesheets_includes_submitted_and_missed_rows() -> None:
    with _session() as session:
        manager_id, ravi_id, anil_id, alpha_id, gamma_id = _seed_team(session)
        week_start = date(2026, 5, 12)
        submitted_week = TimesheetWeekModel(
            user_id=ravi_id,
            week_start_date=week_start,
            status=TimesheetWeekStatus.SUBMITTED,
            total_hours=18,
        )
        session.add(submitted_week)
        session.flush()
        session.add(
            TimesheetEntryModel(
                timesheet_week_id=submitted_week.id,
                project_id=alpha_id,
                hours_worked=18,
                activity_tags=[ActivityTag.BACKEND_API],
            )
        )
        session.add(
            TimesheetWeekModel(
                user_id=anil_id,
                week_start_date=week_start,
                status=TimesheetWeekStatus.MISSED,
                total_hours=0,
            )
        )
        session.commit()
        service = _service(session)

        result = service.list_team_timesheets(manager_id, week_start)

        assert result.total == 2
        submitted = next(row for row in result.rows if row.user_id == ravi_id)
        missed = next(row for row in result.rows if row.user_id == anil_id)
        assert submitted.project_id == alpha_id
        assert submitted.hours == 18
        assert submitted.status == TimesheetWeekStatus.SUBMITTED
        assert missed.project_id == gamma_id
        assert missed.hours == 0
        assert missed.status == TimesheetWeekStatus.MISSED


def test_list_team_timesheets_treats_missing_week_as_missed() -> None:
    with _session() as session:
        manager_id, _, anil_id, _, gamma_id = _seed_team(session)
        week_start = date(2026, 5, 12)
        session.commit()
        service = _service(session)

        result = service.list_team_timesheets(manager_id, week_start)

        anil_row = next(row for row in result.rows if row.user_id == anil_id)
        assert anil_row.project_id == gamma_id
        assert anil_row.hours == 0
        assert anil_row.status == TimesheetWeekStatus.MISSED


def test_get_engineer_timesheet_detail_returns_entries() -> None:
    with _session() as session:
        manager_id, ravi_id, _, alpha_id, _ = _seed_team(session)
        week_start = date(2026, 5, 12)
        week = TimesheetWeekModel(
            user_id=ravi_id,
            week_start_date=week_start,
            status=TimesheetWeekStatus.SUBMITTED,
            total_hours=18,
        )
        session.add(week)
        session.flush()
        session.add(
            TimesheetEntryModel(
                timesheet_week_id=week.id,
                project_id=alpha_id,
                hours_worked=18,
                activity_tags=[ActivityTag.BACKEND_API, ActivityTag.MICROSERVICES],
            )
        )
        session.commit()
        service = _service(session)

        detail = service.get_engineer_timesheet_detail(manager_id, ravi_id, week_start)

        assert detail.status == TimesheetWeekStatus.SUBMITTED
        assert detail.total_hours == 18
        assert len(detail.entries) == 1
        assert detail.entries[0].hours_worked == 18
        assert detail.entries[0].activity_tags == ("Backend Api", "Microservices")


def test_get_engineer_timesheet_detail_returns_missed_when_no_week() -> None:
    with _session() as session:
        manager_id, _, anil_id, _, _ = _seed_team(session)
        week_start = date(2026, 5, 12)
        session.commit()
        service = _service(session)

        detail = service.get_engineer_timesheet_detail(manager_id, anil_id, week_start)

        assert detail.status == TimesheetWeekStatus.MISSED
        assert detail.total_hours == 0
        assert detail.entries == ()


def test_get_engineer_timesheet_detail_raises_when_not_on_team() -> None:
    with _session() as session:
        manager_id, ravi_id, _, _, _ = _seed_team(session)
        seed_rbac(session)
        outsider_id = create_user(
            session,
            full_name="Outsider",
            username="outsider",
            email="outsider@example.test",
            role=Role.ENGINEER,
        )
        session.commit()
        service = _service(session)

        with pytest.raises(UnauthorizedError):
            service.get_engineer_timesheet_detail(
                manager_id,
                outsider_id,
                date(2026, 5, 12),
            )


def test_get_engineer_timesheet_detail_raises_when_employee_missing() -> None:
    with _session() as session:
        manager_id, ravi_id, _, _, _ = _seed_team(session)
        session.commit()
        service = _service(session)

        with pytest.raises(NotFoundError):
            service.get_engineer_timesheet_detail(manager_id, 999, date(2026, 5, 12))
