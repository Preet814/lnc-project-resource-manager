"""Unit tests for APScheduler runner wiring."""

from datetime import date

from sqlalchemy import JSON, create_engine
from sqlalchemy.orm import Session, sessionmaker

from prm.domain.enums import ProjectStatus, Role
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
    SqlAlchemyEmployeeRepository,
    SqlAlchemyProjectRepository,
    SqlAlchemySystemConfigurationRepository,
    SqlAlchemyUserRepository,
)
from prm.infrastructure.security.password import BcryptPasswordHasher
from prm.scheduler.runner import SchedulerRunner


def _session_factory() -> sessionmaker[Session]:
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
    return sessionmaker(bind=engine, autocommit=False, autoflush=False)


def _seed_active_project(session: Session) -> None:
    user_repo = SqlAlchemyUserRepository(session)
    hasher = BcryptPasswordHasher()
    manager = user_repo.create(
        full_name="Manager User",
        username="manager",
        email="manager@example.test",
        password_hash=hasher.hash("TempPass1"),
        role=Role.MANAGER,
    )
    SqlAlchemyProjectRepository(session).create(
        name="Alpha Portal",
        description="Customer portal rewrite",
        start_date=date(2026, 3, 1),
        end_date=date(2026, 6, 30),
        status=ProjectStatus.ACTIVE,
        manager_user_id=manager.id,
    )
    employee_user = user_repo.create(
        full_name="Employee User",
        username="employee",
        email="employee@example.test",
        password_hash=hasher.hash("TempPass1"),
        role=Role.EMPLOYEE,
    )
    SqlAlchemyEmployeeRepository(session).create(
        user_id=employee_user.id,
        full_name="Bench User",
        email="employee@example.test",
        department="Backend",
        designation="Developer",
    )
    SqlAlchemySystemConfigurationRepository(session).create_with_defaults()
    session.commit()


def test_runner_start_and_shutdown_with_injected_job() -> None:
    executed = {"count": 0}

    def run_jobs() -> None:
        executed["count"] += 1

    factory = _session_factory()
    runner = SchedulerRunner(
        factory,
        read_interval_hours=lambda: 4,
        run_jobs=run_jobs,
    )

    runner.start(run_on_startup=True)
    runner.shutdown()

    assert executed["count"] == 1


def test_runner_execute_jobs_updates_project_health() -> None:
    factory = _session_factory()
    with factory() as session:
        _seed_active_project(session)

    runner = SchedulerRunner(factory, read_interval_hours=lambda: 6)
    runner._execute_jobs()

    with factory() as session:
        projects = SqlAlchemyProjectRepository(session).list_all(status=ProjectStatus.ACTIVE)

    assert len(projects) == 1
    assert projects[0].health_computed_at is not None


def test_runner_load_interval_hours_uses_system_configuration() -> None:
    factory = _session_factory()
    with factory() as session:
        SqlAlchemySystemConfigurationRepository(session).create_with_defaults()
        config = SqlAlchemySystemConfigurationRepository(session).find_singleton()
        assert config is not None
        SqlAlchemySystemConfigurationRepository(session).update(
            config.id,
            scheduler_interval_hours=6,
        )
        session.commit()

    runner = SchedulerRunner(factory)

    assert runner._load_interval_hours() == 6
