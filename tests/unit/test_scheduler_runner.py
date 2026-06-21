"""Unit tests for APScheduler runner wiring."""

from datetime import date

from sqlalchemy import JSON
from sqlalchemy.orm import Session, sessionmaker

from prm.api.settings import Settings
from prm.domain.enums import ProjectStatus, Role
from prm.infrastructure.db.models import (
    ProjectHealthSnapshotModel,
)
from prm.infrastructure.db.repositories import (
    SqlAlchemyProjectRepository,
    SqlAlchemySystemConfigurationRepository,
)
from prm.scheduler.runner import SchedulerRunner
from tests.unit.engineer_fixtures import (
    create_allocation_tables,
    create_config_table,
    create_memory_session,
    create_timesheet_tables,
    create_user,
    seed_rbac,
)


def _session_factory() -> sessionmaker[Session]:
    session = create_memory_session(include_project=True)
    engine = session.get_bind()
    create_allocation_tables(session)
    create_config_table(session)
    create_timesheet_tables(session)
    ProjectHealthSnapshotModel.__table__.c.risk_flags.type = JSON()
    ProjectHealthSnapshotModel.__table__.create(engine, checkfirst=True)
    session.close()
    return sessionmaker(bind=engine, autocommit=False, autoflush=False)


def _seed_active_project(session: Session) -> None:
    seed_rbac(session)
    manager_id = create_user(
        session,
        full_name="Manager User",
        username="manager",
        email="manager@example.test",
        role=Role.MANAGER,
    )
    SqlAlchemyProjectRepository(session).create(
        name="Alpha Portal",
        description="Customer portal rewrite",
        start_date=date(2026, 3, 1),
        end_date=date(2026, 6, 30),
        status=ProjectStatus.ACTIVE,
        manager_user_id=manager_id,
    )
    create_user(
        session,
        full_name="Bench User",
        username="employee",
        email="employee@example.test",
        role=Role.ENGINEER,
        manager_id=manager_id,
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


def test_runner_update_interval_hours_reschedules_active_job() -> None:
    executed = {"count": 0}

    def run_jobs() -> None:
        executed["count"] += 1

    factory = _session_factory()
    runner = SchedulerRunner(
        factory,
        read_interval_hours=lambda: 4,
        run_jobs=run_jobs,
    )
    runner.start(run_on_startup=False)

    job = runner._scheduler.get_job("prm_scheduler_tick")
    assert job is not None
    assert job.trigger.interval.total_seconds() == 4 * 3600

    runner.update_interval_hours(6)

    job = runner._scheduler.get_job("prm_scheduler_tick")
    assert job is not None
    assert job.trigger.interval.total_seconds() == 6 * 3600
    assert runner._interval_hours == 6

    runner.update_interval_hours(6)
    runner.shutdown()


def test_registry_reschedule_interval_hours_updates_registered_runner() -> None:
    from prm.scheduler.registry import (
        register_runner,
        reschedule_interval_hours,
        unregister_runner,
    )

    factory = _session_factory()
    runner = SchedulerRunner(factory, read_interval_hours=lambda: 4, run_jobs=lambda: None)
    register_runner(runner)
    runner.start(run_on_startup=False)

    try:
        reschedule_interval_hours(8)
        job = runner._scheduler.get_job("prm_scheduler_tick")
        assert job is not None
        assert job.trigger.interval.total_seconds() == 8 * 3600
    finally:
        unregister_runner()
        runner.shutdown()


def test_runner_registers_timesheet_cron_jobs_when_notifications_enabled() -> None:
    factory = _session_factory()
    settings = Settings(
        bootstrap_admin_username="admin",
        bootstrap_admin_password="AdminPass1",
        bootstrap_admin_full_name="Admin User",
        bootstrap_admin_email="admin@example.test",
        jwt_secret_key="runner-test-secret",
        timesheet_notifications_enabled=True,
    )
    runner = SchedulerRunner(
        factory,
        settings=settings,
        read_interval_hours=lambda: 4,
        run_jobs=lambda: None,
    )
    runner.start(run_on_startup=False)

    try:
        assert runner._scheduler.get_job("timesheet_reminder") is not None
        assert runner._scheduler.get_job("timesheet_freeze") is not None
        assert runner._scheduler.get_job("timesheet_wednesday") is not None
    finally:
        runner.shutdown()


def test_runner_skips_timesheet_cron_jobs_when_notifications_disabled() -> None:
    factory = _session_factory()
    settings = Settings(
        bootstrap_admin_username="admin",
        bootstrap_admin_password="AdminPass1",
        bootstrap_admin_full_name="Admin User",
        bootstrap_admin_email="admin@example.test",
        jwt_secret_key="runner-test-secret",
        timesheet_notifications_enabled=False,
    )
    runner = SchedulerRunner(
        factory,
        settings=settings,
        read_interval_hours=lambda: 4,
        run_jobs=lambda: None,
    )
    runner.start(run_on_startup=False)

    try:
        assert runner._scheduler.get_job("timesheet_reminder") is None
        assert runner._scheduler.get_job("timesheet_freeze") is None
        assert runner._scheduler.get_job("timesheet_wednesday") is None
    finally:
        runner.shutdown()
