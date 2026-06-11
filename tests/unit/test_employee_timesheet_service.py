"""Unit tests for EngineerTimesheetService."""

from datetime import date, timedelta

import pytest
from sqlalchemy import JSON
from sqlalchemy.orm import Session

from prm.application.engineer_timesheet_service import EngineerTimesheetService
from prm.domain.dtos import SubmitTimesheetCommand, SubmitTimesheetEntry
from prm.domain.enums import ActivityTag, AllocationStatus, Role, TimesheetWeekStatus
from prm.domain.exceptions import NotFoundError, ValidationError
from prm.domain.week_calendar import week_start_on_or_before
from prm.infrastructure.db.models import AllocationModel, ProjectModel, TimesheetEntryModel, TimesheetWeekModel
from prm.infrastructure.db.repositories import (
    SqlAlchemyAllocationRepository,
    SqlAlchemyProjectRepository,
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

PAST_MONDAY = date(2026, 5, 11)


def _session() -> Session:
    session = create_memory_session(include_project=True)
    create_allocation_tables(session)
    create_config_table(session)
    create_timesheet_tables(session)
    TimesheetEntryModel.__table__.c.activity_tags.type = JSON()
    return session


def _service(session: Session) -> EngineerTimesheetService:
    return EngineerTimesheetService(
        user_repository=SqlAlchemyUserRepository(session),
        allocation_repository=SqlAlchemyAllocationRepository(session),
        project_repository=SqlAlchemyProjectRepository(session),
        timesheet_repository=SqlAlchemyTimesheetRepository(session),
        config_repository=SqlAlchemySystemConfigurationRepository(session),
    )


def _seed_user_with_allocation(
    session: Session,
    *,
    utilisation_percent: int = 50,
) -> tuple[int, int]:
    """Return (user_id, project_id)."""
    seed_rbac(session)
    manager_id = create_user(
        session,
        full_name="Manager User",
        username="manager",
        email="manager@example.test",
        role=Role.MANAGER,
    )
    user_id = create_user(
        session,
        full_name="Ravi Kumar",
        username="employee",
        email="employee@example.test",
        role=Role.ENGINEER,
        manager_id=manager_id,
    )
    project = ProjectModel(
        name="Alpha Portal",
        description="Test project",
        start_date=date(2026, 1, 1),
        manager_user_id=manager_id,
    )
    session.add(project)
    session.flush()
    session.add(
        AllocationModel(
            user_id=user_id,
            project_id=project.id,
            utilisation_percent=utilisation_percent,
            from_date=date(2026, 1, 1),
            to_date=date(2026, 12, 31),
            status=AllocationStatus.ACTIVE,
            created_by_user_id=manager_id,
        )
    )
    SqlAlchemySystemConfigurationRepository(session).create_with_defaults()
    session.flush()
    return user_id, project.id


def _submit_command(
    project_id: int,
    *,
    week_start: date = PAST_MONDAY,
    hours: int = 18,
) -> SubmitTimesheetCommand:
    return SubmitTimesheetCommand(
        week_start_date=week_start,
        entries=(
            SubmitTimesheetEntry(
                project_id=project_id,
                hours_worked=hours,
                activity_tags=(ActivityTag.MICROSERVICES, ActivityTag.WEBSOCKET),
            ),
        ),
    )


def test_submit_week_persists_submitted_timesheet() -> None:
    with _session() as session:
        user_id, project_id = _seed_user_with_allocation(session)
        session.commit()
        service = _service(session)

        result = service.submit_week(user_id, _submit_command(project_id))

        assert result.status == TimesheetWeekStatus.SUBMITTED
        assert result.total_hours == 18
        assert result.week_start_date == PAST_MONDAY


def test_submit_week_rejects_missing_employee_profile() -> None:
    with _session() as session:
        session.commit()
        service = _service(session)

        with pytest.raises(NotFoundError, match="Engineer profile"):
            service.submit_week(999, _submit_command(1))


def test_submit_week_rejects_non_monday() -> None:
    with _session() as session:
        user_id, project_id = _seed_user_with_allocation(session)
        session.commit()
        service = _service(session)

        with pytest.raises(ValidationError, match="Monday"):
            service.submit_week(
                user_id,
                _submit_command(project_id, week_start=date(2026, 5, 12)),
            )


def test_submit_week_rejects_future_week() -> None:
    with _session() as session:
        user_id, project_id = _seed_user_with_allocation(session)
        session.commit()
        service = _service(session)
        future_monday = week_start_on_or_before(date.today()) + timedelta(days=7)

        with pytest.raises(ValidationError, match="future week"):
            service.submit_week(
                user_id,
                _submit_command(project_id, week_start=future_monday),
            )


def test_submit_week_rejects_duplicate_week() -> None:
    with _session() as session:
        user_id, project_id = _seed_user_with_allocation(session)
        session.add(
            TimesheetWeekModel(
                user_id=user_id,
                week_start_date=PAST_MONDAY,
                status=TimesheetWeekStatus.SUBMITTED,
                total_hours=10,
            )
        )
        session.commit()
        service = _service(session)

        with pytest.raises(ValidationError, match="already exists"):
            service.submit_week(user_id, _submit_command(project_id))


def test_submit_week_rejects_unallocated_project() -> None:
    with _session() as session:
        user_id, project_id = _seed_user_with_allocation(session)
        session.commit()
        service = _service(session)

        with pytest.raises(ValidationError, match="not allocated"):
            service.submit_week(user_id, _submit_command(project_id + 99))


def test_submit_week_rejects_hours_above_allocation_cap() -> None:
    with _session() as session:
        user_id, project_id = _seed_user_with_allocation(
            session, utilisation_percent=50
        )
        session.commit()
        service = _service(session)

        with pytest.raises(ValidationError, match="allocation cap"):
            service.submit_week(user_id, _submit_command(project_id, hours=21))


def test_submit_week_rejects_total_above_max_weekly_hours() -> None:
    with _session() as session:
        user_id, project_a = _seed_user_with_allocation(
            session, utilisation_percent=50
        )
        extra_projects = []
        for name in ("Beta CRM", "Gamma Rewrite"):
            project = ProjectModel(
                name=name,
                description="Extra project",
                start_date=date(2026, 1, 1),
                manager_user_id=1,
            )
            session.add(project)
            session.flush()
            extra_projects.append(project)
            session.add(
                AllocationModel(
                    user_id=user_id,
                    project_id=project.id,
                    utilisation_percent=50,
                    from_date=date(2026, 1, 1),
                    to_date=date(2026, 12, 31),
                    status=AllocationStatus.ACTIVE,
                    created_by_user_id=1,
                )
            )
        config_repo = SqlAlchemySystemConfigurationRepository(session)
        config = config_repo.find_singleton()
        assert config is not None
        config_repo.update(config.id, max_weekly_hours=30)
        session.commit()
        service = _service(session)
        command = SubmitTimesheetCommand(
            week_start_date=PAST_MONDAY,
            entries=(
                SubmitTimesheetEntry(
                    project_id=project_a,
                    hours_worked=10,
                    activity_tags=(ActivityTag.BACKEND_API,),
                ),
                SubmitTimesheetEntry(
                    project_id=extra_projects[0].id,
                    hours_worked=10,
                    activity_tags=(ActivityTag.BUG_FIXING,),
                ),
                SubmitTimesheetEntry(
                    project_id=extra_projects[1].id,
                    hours_worked=11,
                    activity_tags=(ActivityTag.TESTING_QA,),
                ),
            ),
        )

        with pytest.raises(ValidationError, match="weekly maximum"):
            service.submit_week(user_id, command)


def test_submit_week_requires_tags_when_hours_positive() -> None:
    with _session() as session:
        user_id, project_id = _seed_user_with_allocation(session)
        session.commit()
        service = _service(session)
        command = SubmitTimesheetCommand(
            week_start_date=PAST_MONDAY,
            entries=(
                SubmitTimesheetEntry(
                    project_id=project_id,
                    hours_worked=10,
                    activity_tags=(),
                ),
            ),
        )

        with pytest.raises(ValidationError, match="Activity tags"):
            service.submit_week(user_id, command)


def test_list_my_timesheets_returns_submitted_weeks() -> None:
    with _session() as session:
        user_id, project_id = _seed_user_with_allocation(session)
        session.commit()
        service = _service(session)
        service.submit_week(user_id, _submit_command(project_id))

        result = service.list_my_timesheets(user_id)

        assert result.total == 1
        assert result.weeks[0].week_start_date == PAST_MONDAY
        assert result.weeks[0].total_hours == 18


def test_get_my_timesheet_detail_returns_entries() -> None:
    with _session() as session:
        user_id, project_id = _seed_user_with_allocation(session)
        session.commit()
        service = _service(session)
        service.submit_week(user_id, _submit_command(project_id))

        detail = service.get_my_timesheet_detail(user_id, PAST_MONDAY)

        assert detail.status == TimesheetWeekStatus.SUBMITTED
        assert detail.total_hours == 18
        assert len(detail.entries) == 1
        assert detail.entries[0].project_name == "Alpha Portal"
        assert detail.entries[0].activity_tags == ("Microservices", "Websocket")


def test_get_my_timesheet_detail_raises_when_week_missing() -> None:
    with _session() as session:
        user_id, _project_id = _seed_user_with_allocation(session)
        session.commit()
        service = _service(session)

        with pytest.raises(NotFoundError, match="No timesheet found"):
            service.get_my_timesheet_detail(user_id, PAST_MONDAY)
