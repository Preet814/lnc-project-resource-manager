"""Unit tests for SchedulerService."""

from datetime import UTC, date, datetime

from sqlalchemy import JSON, create_engine
from sqlalchemy.orm import Session

from prm.application.health_rule_engine import HealthRuleEngine
from prm.application.scheduler_service import SchedulerService
from prm.application.utilisation_calculator import UtilisationCalculator
from prm.domain.enums import (
    AllocationStatus,
    EmployeeWorkStatus,
    MilestoneStatus,
    ProjectHealthStatus,
    ProjectStatus,
    Role,
    TimesheetWeekStatus,
)
from prm.domain.week_calendar import week_start_on_or_before
from prm.infrastructure.db.models import (
    AllocationModel,
    EmployeeModel,
    MilestoneModel,
    ProjectHealthSnapshotModel,
    ProjectModel,
    SystemConfigurationModel,
    TimesheetWeekModel,
    UserModel,
)
from prm.infrastructure.db.repositories import (
    SqlAlchemyAllocationRepository,
    SqlAlchemyEmployeeRepository,
    SqlAlchemyMilestoneRepository,
    SqlAlchemyProjectHealthSnapshotRepository,
    SqlAlchemyProjectRepository,
    SqlAlchemySystemConfigurationRepository,
    SqlAlchemyTimesheetRepository,
    SqlAlchemyUserRepository,
)
from prm.infrastructure.security.password import BcryptPasswordHasher


def _session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    UserModel.__table__.create(engine, checkfirst=True)
    EmployeeModel.__table__.create(engine, checkfirst=True)
    ProjectModel.__table__.create(engine, checkfirst=True)
    MilestoneModel.__table__.create(engine, checkfirst=True)
    AllocationModel.__table__.create(engine, checkfirst=True)
    SystemConfigurationModel.__table__.create(engine, checkfirst=True)
    TimesheetWeekModel.__table__.create(engine, checkfirst=True)
    ProjectHealthSnapshotModel.__table__.c.risk_flags.type = JSON()
    ProjectHealthSnapshotModel.__table__.create(engine, checkfirst=True)
    return Session(engine)


def _service(session: Session, *, missed_lookback_weeks: int = 4) -> SchedulerService:
    allocation_repo = SqlAlchemyAllocationRepository(session)
    return SchedulerService(
        employee_repository=SqlAlchemyEmployeeRepository(session),
        allocation_repository=allocation_repo,
        project_repository=SqlAlchemyProjectRepository(session),
        milestone_repository=SqlAlchemyMilestoneRepository(session),
        timesheet_repository=SqlAlchemyTimesheetRepository(session),
        health_snapshot_repository=SqlAlchemyProjectHealthSnapshotRepository(session),
        config_repository=SqlAlchemySystemConfigurationRepository(session),
        utilisation=UtilisationCalculator(allocation_repo),
        health_engine=HealthRuleEngine(),
        missed_lookback_weeks=missed_lookback_weeks,
    )


def _seed_manager_and_employee(session: Session) -> tuple[int, int, int]:
    user_repo = SqlAlchemyUserRepository(session)
    hasher = BcryptPasswordHasher()
    manager = user_repo.create(
        full_name="Manager User",
        username="manager",
        email="manager@example.test",
        password_hash=hasher.hash("TempPass1"),
        role=Role.MANAGER,
    )
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
    project = SqlAlchemyProjectRepository(session).create(
        name="Alpha Portal",
        description="Customer portal rewrite",
        start_date=date(2026, 3, 1),
        end_date=date(2026, 6, 30),
        status=ProjectStatus.ACTIVE,
        manager_user_id=manager.id,
    )
    session.flush()
    return manager.id, employee.id, project.id


def test_run_all_jobs_returns_sync_counters() -> None:
    with _session() as session:
        _seed_manager_and_employee(session)
        SqlAlchemySystemConfigurationRepository(session).create_with_defaults()
        session.commit()
        service = _service(session)

        result = service.run_all_jobs(as_of=date(2026, 5, 20))

        assert result.employees_synced == 1
        assert result.projects_evaluated == 1
        assert result.missed_weeks_created == 0


def test_recompute_utilisation_sets_allocated_when_active_allocation_exists() -> None:
    with _session() as session:
        manager_id, employee_id, project_id = _seed_manager_and_employee(session)
        session.add(
            AllocationModel(
                employee_id=employee_id,
                project_id=project_id,
                utilisation_percent=50,
                from_date=date(2026, 3, 1),
                to_date=date(2026, 6, 30),
                created_by_user_id=manager_id,
            )
        )
        session.commit()
        service = _service(session)

        synced = service.recompute_utilisation_and_status(date(2026, 5, 20))

        employee = SqlAlchemyEmployeeRepository(session).find_by_id(employee_id)
        assert synced == 1
        assert employee is not None
        assert employee.current_utilisation_percent == 50
        assert employee.work_status == EmployeeWorkStatus.ALLOCATED


def test_recompute_utilisation_sets_bench_when_no_active_allocation_on_date() -> None:
    with _session() as session:
        manager_id, employee_id, project_id = _seed_manager_and_employee(session)
        session.add(
            AllocationModel(
                employee_id=employee_id,
                project_id=project_id,
                utilisation_percent=50,
                from_date=date(2026, 3, 1),
                to_date=date(2026, 5, 10),
                status=AllocationStatus.ENDED,
                created_by_user_id=manager_id,
            )
        )
        employee_repo = SqlAlchemyEmployeeRepository(session)
        employee_repo.update_utilisation_and_status(
            employee_id,
            current_utilisation_percent=50,
            work_status=EmployeeWorkStatus.ALLOCATED,
        )
        session.commit()
        service = _service(session)

        service.recompute_utilisation_and_status(date(2026, 5, 20))

        employee = employee_repo.find_by_id(employee_id)
        assert employee is not None
        assert employee.current_utilisation_percent == 0
        assert employee.work_status == EmployeeWorkStatus.BENCH


def test_recompute_project_health_persists_status_and_snapshot() -> None:
    with _session() as session:
        _, employee_id, project_id = _seed_manager_and_employee(session)
        session.add(
            MilestoneModel(
                project_id=project_id,
                title="Backend API",
                due_date=date(2026, 5, 15),
                status=MilestoneStatus.IN_PROGRESS,
                sequence_order=1,
            )
        )
        session.commit()
        service = _service(session)

        evaluated = service.recompute_project_health(date(2026, 5, 20))

        project = SqlAlchemyProjectRepository(session).find_by_id(project_id)
        snapshot = SqlAlchemyProjectHealthSnapshotRepository(
            session
        ).find_latest_for_project(project_id)

        assert evaluated == 1
        assert project is not None
        assert project.health_status == ProjectHealthStatus.AT_RISK
        assert project.health_computed_at is not None
        assert snapshot is not None
        assert snapshot.status == ProjectHealthStatus.AT_RISK
        assert snapshot.risk_flags[0] == "Backend API milestone is 5 days overdue"


def test_recompute_project_health_skips_completed_projects() -> None:
    with _session() as session:
        manager_id, _, _active_project_id = _seed_manager_and_employee(session)
        project_repo = SqlAlchemyProjectRepository(session)
        completed = project_repo.create(
            name="Finished Portal",
            description="Delivered",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 6, 30),
            status=ProjectStatus.COMPLETED,
            manager_user_id=manager_id,
        )
        session.add(
            MilestoneModel(
                project_id=completed.id,
                title="Backend API",
                due_date=date(2026, 5, 15),
                status=MilestoneStatus.IN_PROGRESS,
                sequence_order=1,
            )
        )
        session.commit()
        service = _service(session)

        evaluated = service.recompute_project_health(date(2026, 5, 20))

        completed_project = project_repo.find_by_id(completed.id)
        snapshot = SqlAlchemyProjectHealthSnapshotRepository(
            session
        ).find_latest_for_project(completed.id)

        assert evaluated == 1
        assert completed_project is not None
        assert completed_project.health_computed_at is None
        assert snapshot is None


def test_flag_missed_timesheets_creates_row_for_closed_week_with_allocation() -> None:
    with _session() as session:
        manager_id, employee_id, project_id = _seed_manager_and_employee(session)
        session.add(
            AllocationModel(
                employee_id=employee_id,
                project_id=project_id,
                utilisation_percent=50,
                from_date=date(2026, 3, 1),
                to_date=date(2026, 6, 30),
                created_by_user_id=manager_id,
            )
        )
        session.commit()
        service = _service(session, missed_lookback_weeks=1)
        as_of = date(2026, 5, 19)
        expected_week = SchedulerService._last_completed_week_start(as_of)
        assert expected_week is not None

        created = service.flag_missed_timesheets(as_of)
        session.commit()

        timesheets = SqlAlchemyTimesheetRepository(session)
        week = timesheets.find_week_by_employee(employee_id, expected_week)

        assert created == 1
        assert week is not None
        assert week.status == TimesheetWeekStatus.MISSED
        assert week.total_hours == 0


def test_flag_missed_timesheets_catchup_creates_multiple_closed_weeks() -> None:
    with _session() as session:
        manager_id, employee_id, project_id = _seed_manager_and_employee(session)
        session.add(
            AllocationModel(
                employee_id=employee_id,
                project_id=project_id,
                utilisation_percent=50,
                from_date=date(2026, 3, 1),
                to_date=date(2026, 6, 30),
                created_by_user_id=manager_id,
            )
        )
        session.commit()
        service = _service(session, missed_lookback_weeks=4)

        created = service.flag_missed_timesheets(date(2026, 5, 19))

        assert created == 4


def test_flag_missed_timesheets_skips_when_submitted_week_exists() -> None:
    with _session() as session:
        manager_id, employee_id, project_id = _seed_manager_and_employee(session)
        session.add(
            AllocationModel(
                employee_id=employee_id,
                project_id=project_id,
                utilisation_percent=50,
                from_date=date(2026, 3, 1),
                to_date=date(2026, 6, 30),
                created_by_user_id=manager_id,
            )
        )
        as_of = date(2026, 5, 19)
        submitted_week = SchedulerService._last_completed_week_start(as_of)
        assert submitted_week is not None
        session.add(
            TimesheetWeekModel(
                employee_id=employee_id,
                week_start_date=submitted_week,
                status=TimesheetWeekStatus.SUBMITTED,
                total_hours=20,
                submitted_at=datetime(2026, 5, 16, 12, 0, tzinfo=UTC),
            )
        )
        session.commit()
        service = _service(session, missed_lookback_weeks=1)

        created = service.flag_missed_timesheets(as_of)
        session.commit()

        assert created == 0


def test_flag_missed_timesheets_skips_current_week() -> None:
    with _session() as session:
        manager_id, employee_id, project_id = _seed_manager_and_employee(session)
        session.add(
            AllocationModel(
                employee_id=employee_id,
                project_id=project_id,
                utilisation_percent=50,
                from_date=date(2026, 3, 1),
                to_date=date(2026, 6, 30),
                created_by_user_id=manager_id,
            )
        )
        session.commit()
        service = _service(session, missed_lookback_weeks=1)
        timesheets = SqlAlchemyTimesheetRepository(session)
        as_of = date(2026, 5, 14)
        current_week_start = week_start_on_or_before(as_of)
        last_completed_week_start = SchedulerService._last_completed_week_start(as_of)
        assert last_completed_week_start is not None

        created = service.flag_missed_timesheets(as_of)
        session.commit()

        current_week = timesheets.find_week_by_employee(employee_id, current_week_start)
        last_completed_week = timesheets.find_week_by_employee(
            employee_id,
            last_completed_week_start,
        )

        assert current_week is None
        assert created == 1
        assert last_completed_week is not None
        assert last_completed_week.status == TimesheetWeekStatus.MISSED
