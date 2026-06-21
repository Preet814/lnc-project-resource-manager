"""Unit tests for TimesheetRestoreService."""

from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy.orm import Session

from prm.application.timesheet_restore_service import TimesheetRestoreService
from prm.domain.enums import ProjectStatus, Role, TimesheetWeekStatus
from prm.domain.exceptions import UnauthorizedError, ValidationError
from prm.domain.week_calendar import last_completed_week_start
from prm.infrastructure.db.models import AllocationModel, TimesheetWeekModel
from prm.infrastructure.db.repositories import (
    SqlAlchemyAllocationRepository,
    SqlAlchemyTimesheetRepository,
    SqlAlchemyTimesheetSubmissionRestoreRepository,
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
    *,
    email_sender: FakeEmailSender | None = None,
    now_provider=None,
) -> TimesheetRestoreService:
    return TimesheetRestoreService(
        user_repository=SqlAlchemyUserRepository(session),
        timesheet_repository=SqlAlchemyTimesheetRepository(session),
        restore_repository=SqlAlchemyTimesheetSubmissionRestoreRepository(session),
        email_sender=email_sender or FakeEmailSender(),
        notifications_enabled=True,
        app_timezone="Asia/Kolkata",
        now_provider=now_provider,
    )


def _seed_manager_and_engineer(session: Session) -> tuple[int, int]:
    seed_rbac(session)
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
    SqlAlchemyUserRepository(session).update_email_verified(manager_id, email_verified=True)
    SqlAlchemyUserRepository(session).update_email_verified(engineer_id, email_verified=True)

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
    return manager_id, engineer_id


def test_restore_submission_access_clears_missed_and_sends_email() -> None:
    with _session() as session:
        manager_id, engineer_id = _seed_manager_and_engineer(session)
        as_of = date(2026, 5, 20)
        week_start = last_completed_week_start(as_of)
        assert week_start is not None
        session.add(
            TimesheetWeekModel(
                user_id=engineer_id,
                week_start_date=week_start,
                status=TimesheetWeekStatus.MISSED,
                total_hours=0,
            )
        )
        session.commit()
        sender = FakeEmailSender()
        after_freeze = datetime(2026, 5, 21, 9, 0, tzinfo=ZoneInfo("Asia/Kolkata"))
        service = _service(session, email_sender=sender, now_provider=lambda: after_freeze)

        result = service.restore_submission_access(manager_id, engineer_id, week_start)
        session.commit()

        week = SqlAlchemyTimesheetRepository(session).find_week_by_user(
            engineer_id,
            week_start,
        )
        assert week is None
        assert result.user_id == engineer_id
        assert len(sender.messages) == 1
        assert sender.messages[0][0] == "employee@example.test"


def test_restore_submission_access_rejects_non_reporting_manager() -> None:
    with _session() as session:
        manager_id, engineer_id = _seed_manager_and_engineer(session)
        other_manager_id = create_user(
            session,
            username="other",
            email="other@example.test",
            full_name="Other Manager",
            role=Role.MANAGER,
        )
        session.commit()
        as_of = date(2026, 5, 20)
        week_start = last_completed_week_start(as_of)
        assert week_start is not None
        after_freeze = datetime(2026, 5, 21, 9, 0, tzinfo=ZoneInfo("Asia/Kolkata"))
        service = _service(session, now_provider=lambda: after_freeze)

        with pytest.raises(UnauthorizedError, match="reporting manager"):
            service.restore_submission_access(other_manager_id, engineer_id, week_start)


def test_get_access_state_marks_can_restore_for_reporting_manager() -> None:
    with _session() as session:
        manager_id, engineer_id = _seed_manager_and_engineer(session)
        session.commit()
        as_of = date(2026, 5, 20)
        week_start = last_completed_week_start(as_of)
        assert week_start is not None
        after_freeze = datetime(2026, 5, 21, 9, 0, tzinfo=ZoneInfo("Asia/Kolkata"))
        service = _service(session, now_provider=lambda: after_freeze)

        state = service.get_access_state(manager_id, engineer_id, week_start)

        assert state.submission_frozen is True
        assert state.submission_restored is False
        assert state.can_restore is True


def test_restore_submission_access_rejects_before_freeze() -> None:
    with _session() as session:
        manager_id, engineer_id = _seed_manager_and_engineer(session)
        session.commit()
        as_of = date(2026, 5, 20)
        week_start = last_completed_week_start(as_of)
        assert week_start is not None
        before_freeze = datetime(2026, 5, 19, 12, 0, tzinfo=ZoneInfo("Asia/Kolkata"))
        service = _service(session, now_provider=lambda: before_freeze)

        with pytest.raises(ValidationError, match="not restricted"):
            service.restore_submission_access(manager_id, engineer_id, week_start)
