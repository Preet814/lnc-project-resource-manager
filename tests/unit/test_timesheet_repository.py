"""Unit tests for SQLAlchemy timesheet repository manager read methods."""

from datetime import UTC, date, datetime

from sqlalchemy import JSON, create_engine
from sqlalchemy.orm import Session

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
