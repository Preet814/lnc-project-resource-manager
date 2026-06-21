"""Unit tests for TimesheetNotificationService."""

from datetime import UTC, date, datetime

from sqlalchemy.orm import Session

from prm.application.timesheet_notification_service import TimesheetNotificationService
from prm.domain.constants import (
    TIMESHEET_ENGINEER_REMINDER_SUBJECT,
    TIMESHEET_MANAGER_DIGEST_SUBJECT,
)
from prm.domain.enums import ProjectStatus, Role, TimesheetWeekStatus
from prm.domain.week_calendar import last_completed_week_start
from prm.infrastructure.db.models import AllocationModel, TimesheetWeekModel
from prm.infrastructure.db.repositories import (
    SqlAlchemyAllocationRepository,
    SqlAlchemySystemConfigurationRepository,
    SqlAlchemyTimesheetRepository,
    SqlAlchemyUserRepository,
)
from tests.unit.engineer_fixtures import (
    create_allocation_tables,
    create_config_table,
    create_memory_session,
    create_timesheet_tables,
    create_user,
    seed_rbac,
)
from tests.unit.test_email_verification_service import FakeEmailSender


def _session() -> Session:
    session = create_memory_session(include_project=True)
    create_allocation_tables(session)
    create_config_table(session)
    create_timesheet_tables(session)
    return session


def _service(
    session: Session,
    email_sender: FakeEmailSender,
    *,
    notifications_enabled: bool = True,
) -> TimesheetNotificationService:
    return TimesheetNotificationService(
        user_repository=SqlAlchemyUserRepository(session),
        allocation_repository=SqlAlchemyAllocationRepository(session),
        timesheet_repository=SqlAlchemyTimesheetRepository(session),
        email_sender=email_sender,
        notifications_enabled=notifications_enabled,
    )


def _seed_engineer_with_allocation(
    session: Session,
    *,
    engineer_email_verified: bool = True,
    manager_email_verified: bool = True,
) -> tuple[int, int, int]:
    seed_rbac(session)
    user_repo = SqlAlchemyUserRepository(session)
    manager_id = create_user(
        session,
        username="manager",
        email="manager@example.test",
        full_name="Manager User",
        role=Role.MANAGER,
    )
    engineer_id = create_user(
        session,
        username="employee",
        email="employee@example.test",
        full_name="Ravi Kumar",
        role=Role.ENGINEER,
        manager_id=manager_id,
    )
    if manager_email_verified:
        user_repo.update_email_verified(manager_id, email_verified=True)
    if engineer_email_verified:
        user_repo.update_email_verified(engineer_id, email_verified=True)

    from prm.infrastructure.db.repositories import SqlAlchemyProjectRepository

    project = SqlAlchemyProjectRepository(session).create(
        name="Alpha Portal",
        description="Customer portal rewrite",
        start_date=date(2026, 3, 1),
        end_date=date(2026, 6, 30),
        status=ProjectStatus.ACTIVE,
        manager_user_id=manager_id,
    )
    session.add(
        AllocationModel(
            user_id=engineer_id,
            project_id=project.id,
            utilisation_percent=50,
            from_date=date(2026, 3, 1),
            to_date=date(2026, 6, 30),
            created_by_user_id=manager_id,
        )
    )
    session.flush()
    return manager_id, engineer_id, project.id


def test_find_engineers_missing_last_completed_week() -> None:
    with _session() as session:
        _, engineer_id, _ = _seed_engineer_with_allocation(session)
        session.commit()
        service = _service(session, FakeEmailSender())
        as_of = date(2026, 5, 20)
        expected_week = last_completed_week_start(as_of)
        assert expected_week is not None

        targets = service.find_engineers_missing_last_completed_week(as_of)

        assert len(targets) == 1
        assert targets[0].user_id == engineer_id
        assert targets[0].week_start_date == expected_week


def test_send_engineer_reminders_skips_unverified_email() -> None:
    with _session() as session:
        _seed_engineer_with_allocation(session, engineer_email_verified=False)
        session.commit()
        sender = FakeEmailSender()
        service = _service(session, sender)

        sent = service.send_engineer_reminders(date(2026, 5, 20))

        assert sent == 0
        assert sender.messages == []


def test_send_engineer_reminders_sends_to_verified_engineer() -> None:
    with _session() as session:
        _seed_engineer_with_allocation(session, engineer_email_verified=True)
        session.commit()
        sender = FakeEmailSender()
        service = _service(session, sender)

        sent = service.send_engineer_reminders(date(2026, 5, 20))

        assert sent == 1
        assert len(sender.messages) == 1
        assert sender.messages[0][0] == "employee@example.test"
        assert sender.messages[0][1] == TIMESHEET_ENGINEER_REMINDER_SUBJECT


def test_send_engineer_reminders_skips_submitted_week() -> None:
    with _session() as session:
        _, engineer_id, _ = _seed_engineer_with_allocation(session)
        as_of = date(2026, 5, 20)
        week_start = last_completed_week_start(as_of)
        assert week_start is not None
        session.add(
            TimesheetWeekModel(
                user_id=engineer_id,
                week_start_date=week_start,
                status=TimesheetWeekStatus.SUBMITTED,
                total_hours=20,
                submitted_at=datetime(2026, 5, 16, 12, 0, tzinfo=UTC),
            )
        )
        session.commit()
        sender = FakeEmailSender()
        service = _service(session, sender)

        sent = service.send_engineer_reminders(as_of)

        assert sent == 0
        assert sender.messages == []


def test_send_manager_digests_groups_by_manager() -> None:
    with _session() as session:
        _seed_engineer_with_allocation(session, manager_email_verified=True)
        session.commit()
        sender = FakeEmailSender()
        service = _service(session, sender)

        sent = service.send_manager_digests(date(2026, 5, 20))

        assert sent == 1
        assert len(sender.messages) == 1
        assert sender.messages[0][0] == "manager@example.test"
        assert sender.messages[0][1] == TIMESHEET_MANAGER_DIGEST_SUBJECT
        assert "Ravi Kumar" in sender.messages[0][2]


def test_send_manager_digests_skips_unverified_manager() -> None:
    with _session() as session:
        _seed_engineer_with_allocation(session, manager_email_verified=False)
        session.commit()
        sender = FakeEmailSender()
        service = _service(session, sender)

        sent = service.send_manager_digests(date(2026, 5, 20))

        assert sent == 0
        assert sender.messages == []


def test_flag_missed_for_last_completed_week_creates_row() -> None:
    with _session() as session:
        _, engineer_id, _ = _seed_engineer_with_allocation(session)
        session.commit()
        service = _service(session, FakeEmailSender())
        as_of = date(2026, 5, 20)
        week_start = last_completed_week_start(as_of)
        assert week_start is not None

        created = service.flag_missed_for_last_completed_week(as_of)
        session.commit()

        week = SqlAlchemyTimesheetRepository(session).find_week_by_user(
            engineer_id,
            week_start,
        )

        assert created == 1
        assert week is not None
        assert week.status == TimesheetWeekStatus.MISSED


def test_notifications_disabled_skips_email_send() -> None:
    with _session() as session:
        _seed_engineer_with_allocation(session)
        session.commit()
        sender = FakeEmailSender()
        service = _service(session, sender, notifications_enabled=False)

        assert service.send_engineer_reminders(date(2026, 5, 20)) == 0
        assert service.send_manager_digests(date(2026, 5, 20)) == 0
        assert sender.messages == []


def test_run_wednesday_jobs_returns_counts() -> None:
    with _session() as session:
        _seed_engineer_with_allocation(session)
        session.commit()
        service = _service(session, FakeEmailSender())

        reminders, digests, missed = service.run_wednesday_jobs(date(2026, 5, 20))

        assert reminders == 1
        assert digests == 1
        assert missed == 1


def test_find_engineers_missing_skips_bench_engineer_without_allocation() -> None:
    with _session() as session:
        seed_rbac(session)
        manager_id = create_user(
            session,
            username="manager",
            email="manager@example.test",
            full_name="Manager User",
            role=Role.MANAGER,
        )
        create_user(
            session,
            username="bench",
            email="bench@example.test",
            full_name="Bench User",
            role=Role.ENGINEER,
            manager_id=manager_id,
        )
        session.commit()
        service = _service(session, FakeEmailSender())

        targets = service.find_engineers_missing_last_completed_week(date(2026, 5, 20))

        assert targets == []
