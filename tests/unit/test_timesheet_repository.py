"""Unit tests for SQLAlchemy timesheet repository manager read methods."""

from datetime import UTC, date, datetime

from sqlalchemy import JSON, create_engine
from sqlalchemy.orm import Session

from prm.domain.entities.timesheet import NewTimesheetEntry
from prm.domain.enums import ActivityTag, Role, TimesheetWeekStatus
from prm.infrastructure.db.models import (
    EmployeeModel,
    ProjectModel,
    TimesheetEntryModel,
    TimesheetWeekModel,
    UserModel,
)
from prm.infrastructure.db.repositories import (
    SqlAlchemyEmployeeRepository,
    SqlAlchemyTimesheetRepository,
    SqlAlchemyUserRepository,
)
from prm.infrastructure.security.password import BcryptPasswordHasher


def _session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    UserModel.__table__.create(engine, checkfirst=True)
    EmployeeModel.__table__.create(engine, checkfirst=True)
    ProjectModel.__table__.create(engine, checkfirst=True)
    TimesheetWeekModel.__table__.create(engine, checkfirst=True)
    TimesheetEntryModel.__table__.c.activity_tags.type = JSON()
    TimesheetEntryModel.__table__.create(engine, checkfirst=True)
    return Session(engine)


def _seed_employee(session: Session) -> int:
    user_repo = SqlAlchemyUserRepository(session)
    hasher = BcryptPasswordHasher()
    employee_user = user_repo.create(
        full_name="Employee User",
        username="employee",
        email="employee@example.test",
        password_hash=hasher.hash("TempPass1"),
        role=Role.EMPLOYEE,
    )
    employee_repo = SqlAlchemyEmployeeRepository(session)
    employee = employee_repo.create(
        user_id=employee_user.id,
        full_name="Ravi Kumar",
        email="employee@example.test",
        department="Backend",
        designation="Developer",
    )
    session.flush()
    return employee.id


def _seed_project(session: Session) -> int:
    user_repo = SqlAlchemyUserRepository(session)
    hasher = BcryptPasswordHasher()
    manager = user_repo.create(
        full_name="Manager User",
        username="manager",
        email="manager@example.test",
        password_hash=hasher.hash("TempPass1"),
        role=Role.MANAGER,
    )
    project = ProjectModel(
        name="Alpha Portal",
        description="Test project",
        start_date=date(2026, 1, 1),
        manager_user_id=manager.id,
    )
    session.add(project)
    session.flush()
    return project.id


def test_find_week_by_employee_returns_domain_week() -> None:
    with _session() as session:
        employee_id = _seed_employee(session)
        week_start = date(2026, 5, 12)
        session.add(
            TimesheetWeekModel(
                employee_id=employee_id,
                week_start_date=week_start,
                status=TimesheetWeekStatus.SUBMITTED,
                total_hours=38,
                submitted_at=datetime(2026, 5, 16, 12, 0, tzinfo=UTC),
            )
        )
        session.commit()
        repo = SqlAlchemyTimesheetRepository(session)

        week = repo.find_week_by_employee(employee_id, week_start)

        assert week is not None
        assert week.status == TimesheetWeekStatus.SUBMITTED
        assert week.total_hours == 38


def test_find_week_by_employee_returns_none_when_missing() -> None:
    with _session() as session:
        employee_id = _seed_employee(session)
        session.commit()
        repo = SqlAlchemyTimesheetRepository(session)

        assert repo.find_week_by_employee(employee_id, date(2026, 5, 12)) is None


def test_list_entries_for_week_returns_project_lines() -> None:
    with _session() as session:
        employee_id = _seed_employee(session)
        project_id = _seed_project(session)
        week = TimesheetWeekModel(
            employee_id=employee_id,
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


def test_list_weeks_for_employee_orders_by_week_start_desc() -> None:
    with _session() as session:
        employee_id = _seed_employee(session)
        session.add_all(
            [
                TimesheetWeekModel(
                    employee_id=employee_id,
                    week_start_date=date(2026, 5, 5),
                    status=TimesheetWeekStatus.SUBMITTED,
                    total_hours=40,
                ),
                TimesheetWeekModel(
                    employee_id=employee_id,
                    week_start_date=date(2026, 5, 12),
                    status=TimesheetWeekStatus.SUBMITTED,
                    total_hours=38,
                ),
            ]
        )
        session.commit()
        repo = SqlAlchemyTimesheetRepository(session)

        weeks = repo.list_weeks_for_employee(employee_id)

        assert len(weeks) == 2
        assert weeks[0].week_start_date == date(2026, 5, 12)
        assert weeks[1].week_start_date == date(2026, 5, 5)


def test_list_weeks_for_employee_respects_limit() -> None:
    with _session() as session:
        employee_id = _seed_employee(session)
        session.add_all(
            [
                TimesheetWeekModel(
                    employee_id=employee_id,
                    week_start_date=date(2026, 5, 5),
                    status=TimesheetWeekStatus.SUBMITTED,
                    total_hours=40,
                ),
                TimesheetWeekModel(
                    employee_id=employee_id,
                    week_start_date=date(2026, 5, 12),
                    status=TimesheetWeekStatus.SUBMITTED,
                    total_hours=38,
                ),
            ]
        )
        session.commit()
        repo = SqlAlchemyTimesheetRepository(session)

        weeks = repo.list_weeks_for_employee(employee_id, limit=1)

        assert len(weeks) == 1
        assert weeks[0].week_start_date == date(2026, 5, 12)


def test_create_week_with_entries_persists_week_and_lines() -> None:
    with _session() as session:
        employee_id = _seed_employee(session)
        project_id = _seed_project(session)
        session.commit()
        repo = SqlAlchemyTimesheetRepository(session)
        submitted_at = datetime(2026, 5, 16, 9, 30, tzinfo=UTC)
        week_start = date(2026, 5, 12)

        week = repo.create_week_with_entries(
            employee_id=employee_id,
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
        # SQLite in-memory tests store datetimes without tzinfo
        assert week.submitted_at == submitted_at.replace(tzinfo=None)

        found = repo.find_week_by_employee(employee_id, week_start)
        assert found is not None
        assert found.id == week.id

        entries = repo.list_entries_for_week(week.id)
        assert len(entries) == 2
        assert entries[0].hours_worked == 18
        assert entries[1].activity_tags == (ActivityTag.BACKEND_API,)


def test_create_missed_week_persists_missed_status_without_entries() -> None:
    with _session() as session:
        employee_id = _seed_employee(session)
        session.commit()
        repo = SqlAlchemyTimesheetRepository(session)
        week_start = date(2026, 4, 21)

        week = repo.create_missed_week(
            employee_id=employee_id,
            week_start_date=week_start,
        )
        session.commit()

        assert week.id > 0
        assert week.status == TimesheetWeekStatus.MISSED
        assert week.total_hours == 0
        assert week.submitted_at is None

        found = repo.find_week_by_employee(employee_id, week_start)
        assert found is not None
        assert found.id == week.id
        assert found.status == TimesheetWeekStatus.MISSED

        entries = repo.list_entries_for_week(week.id)
        assert entries == []
