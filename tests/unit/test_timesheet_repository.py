"""Unit tests for SQLAlchemy timesheet repository manager read methods."""

from datetime import UTC, date, datetime

from sqlalchemy import JSON
from sqlalchemy.orm import Session

from prm.domain.entities.timesheet import NewTimesheetEntry
from prm.domain.enums import ActivityTag, Role, TimesheetWeekStatus
from prm.infrastructure.db.models import ProjectModel, TimesheetEntryModel, TimesheetWeekModel
from prm.infrastructure.db.repositories import SqlAlchemyTimesheetRepository
from tests.unit.engineer_fixtures import (
    create_memory_session,
    create_timesheet_tables,
    create_user,
    seed_rbac,
)


def _session() -> Session:
    session = create_memory_session(include_project=True)
    create_timesheet_tables(session)
    TimesheetEntryModel.__table__.c.activity_tags.type = JSON()
    return session


def _seed_user(session: Session) -> int:
    seed_rbac(session)
    return create_user(
        session,
        full_name="Ravi Kumar",
        username="employee",
        email="employee@example.test",
        role=Role.ENGINEER,
    )


def _seed_project(session: Session) -> int:
    seed_rbac(session)
    manager_id = create_user(
        session,
        full_name="Manager User",
        username="manager",
        email="manager@example.test",
        role=Role.MANAGER,
    )
    project = ProjectModel(
        name="Alpha Portal",
        description="Test project",
        start_date=date(2026, 1, 1),
        manager_user_id=manager_id,
    )
    session.add(project)
    session.flush()
    return project.id


def test_find_week_by_user_returns_domain_week() -> None:
    with _session() as session:
        user_id = _seed_user(session)
        week_start = date(2026, 5, 12)
        session.add(
            TimesheetWeekModel(
                user_id=user_id,
                week_start_date=week_start,
                status=TimesheetWeekStatus.SUBMITTED,
                total_hours=38,
                submitted_at=datetime(2026, 5, 16, 12, 0, tzinfo=UTC),
            )
        )
        session.commit()
        repo = SqlAlchemyTimesheetRepository(session)

        week = repo.find_week_by_user(user_id, week_start)

        assert week is not None
        assert week.status == TimesheetWeekStatus.SUBMITTED
        assert week.total_hours == 38


def test_find_week_by_user_returns_none_when_missing() -> None:
    with _session() as session:
        user_id = _seed_user(session)
        session.commit()
        repo = SqlAlchemyTimesheetRepository(session)

        assert repo.find_week_by_user(user_id, date(2026, 5, 12)) is None


def test_list_entries_for_week_returns_project_lines() -> None:
    with _session() as session:
        user_id = _seed_user(session)
        project_id = _seed_project(session)
        week = TimesheetWeekModel(
            user_id=user_id,
            week_start_date=date(2026, 5, 12),
            status=TimesheetWeekStatus.SUBMITTED,
            total_hours=18,
        )
        session.add(week)
        session.flush()
        session.add(
            TimesheetEntryModel(
                timesheet_week_id=week.id,
                project_id=project_id,
                hours_worked=18,
                activity_tags=[ActivityTag.BACKEND_API, ActivityTag.MICROSERVICES],
            )
        )
        session.commit()
        repo = SqlAlchemyTimesheetRepository(session)

        entries = repo.list_entries_for_week(week.id)

        assert len(entries) == 1
        assert entries[0].project_id == project_id
        assert entries[0].hours_worked == 18
        assert entries[0].activity_tags == (ActivityTag.BACKEND_API, ActivityTag.MICROSERVICES)


def test_list_weeks_for_user_orders_by_week_start_desc() -> None:
    with _session() as session:
        user_id = _seed_user(session)
        session.add_all(
            [
                TimesheetWeekModel(
                    user_id=user_id,
                    week_start_date=date(2026, 5, 5),
                    status=TimesheetWeekStatus.SUBMITTED,
                    total_hours=40,
                ),
                TimesheetWeekModel(
                    user_id=user_id,
                    week_start_date=date(2026, 5, 12),
                    status=TimesheetWeekStatus.SUBMITTED,
                    total_hours=38,
                ),
            ]
        )
        session.commit()
        repo = SqlAlchemyTimesheetRepository(session)

        weeks = repo.list_weeks_for_user(user_id)

        assert len(weeks) == 2
        assert weeks[0].week_start_date == date(2026, 5, 12)
        assert weeks[1].week_start_date == date(2026, 5, 5)


def test_list_weeks_for_user_respects_limit() -> None:
    with _session() as session:
        user_id = _seed_user(session)
        session.add_all(
            [
                TimesheetWeekModel(
                    user_id=user_id,
                    week_start_date=date(2026, 5, 5),
                    status=TimesheetWeekStatus.SUBMITTED,
                    total_hours=40,
                ),
                TimesheetWeekModel(
                    user_id=user_id,
                    week_start_date=date(2026, 5, 12),
                    status=TimesheetWeekStatus.SUBMITTED,
                    total_hours=38,
                ),
            ]
        )
        session.commit()
        repo = SqlAlchemyTimesheetRepository(session)

        weeks = repo.list_weeks_for_user(user_id, limit=1)

        assert len(weeks) == 1
        assert weeks[0].week_start_date == date(2026, 5, 12)


def test_create_week_with_entries_persists_week_and_lines() -> None:
    with _session() as session:
        user_id = _seed_user(session)
        project_id = _seed_project(session)
        session.commit()
        repo = SqlAlchemyTimesheetRepository(session)
        submitted_at = datetime(2026, 5, 16, 9, 30, tzinfo=UTC)
        week_start = date(2026, 5, 12)

        week = repo.create_week_with_entries(
            user_id=user_id,
            week_start_date=week_start,
            total_hours=38,
            submitted_at=submitted_at,
            entries=(
                NewTimesheetEntry(
                    project_id=project_id,
                    hours_worked=18,
                    activity_tags=(ActivityTag.MICROSERVICES, ActivityTag.WEBSOCKET),
                ),
                NewTimesheetEntry(
                    project_id=project_id,
                    hours_worked=20,
                    activity_tags=(ActivityTag.BACKEND_API,),
                ),
            ),
        )
        session.commit()

        assert week.id > 0
        assert week.status == TimesheetWeekStatus.SUBMITTED
        assert week.total_hours == 38
        assert week.submitted_at is not None
        assert week.submitted_at == submitted_at.replace(tzinfo=None)

        found = repo.find_week_by_user(user_id, week_start)
        assert found is not None
        assert found.id == week.id

        entries = repo.list_entries_for_week(week.id)
        assert len(entries) == 2
        assert entries[0].hours_worked == 18
        assert entries[1].activity_tags == (ActivityTag.BACKEND_API,)


def test_create_missed_week_persists_missed_status_without_entries() -> None:
    with _session() as session:
        user_id = _seed_user(session)
        session.commit()
        repo = SqlAlchemyTimesheetRepository(session)
        week_start = date(2026, 4, 21)

        week = repo.create_missed_week(
            user_id=user_id,
            week_start_date=week_start,
        )
        session.commit()

        assert week.id > 0
        assert week.status == TimesheetWeekStatus.MISSED
        assert week.total_hours == 0
        assert week.submitted_at is None

        found = repo.find_week_by_user(user_id, week_start)
        assert found is not None
        assert found.id == week.id
        assert found.status == TimesheetWeekStatus.MISSED

        entries = repo.list_entries_for_week(week.id)
        assert entries == []
