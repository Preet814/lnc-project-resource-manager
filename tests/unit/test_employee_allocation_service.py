"""Unit tests for EngineerAllocationService."""

from datetime import date

import pytest
from sqlalchemy.orm import Session

from prm.application.engineer_allocation_service import EngineerAllocationService
from prm.domain.enums import AllocationStatus, Role
from prm.domain.exceptions import NotFoundError, ValidationError
from prm.infrastructure.db.models import AllocationModel, ProjectModel
from prm.infrastructure.db.repositories import (
    SqlAlchemyAllocationRepository,
    SqlAlchemyProjectRepository,
    SqlAlchemySystemConfigurationRepository,
    SqlAlchemyUserRepository,
)
from tests.unit.engineer_fixtures import (
    create_allocation_tables,
    create_config_table,
    create_memory_session,
    create_user,
    seed_rbac,
)

PAST_MONDAY = date(2026, 5, 11)


def _session() -> Session:
    session = create_memory_session(include_project=True)
    create_allocation_tables(session)
    create_config_table(session)
    return session


def _service(session: Session) -> EngineerAllocationService:
    return EngineerAllocationService(
        user_repository=SqlAlchemyUserRepository(session),
        allocation_repository=SqlAlchemyAllocationRepository(session),
        project_repository=SqlAlchemyProjectRepository(session),
        config_repository=SqlAlchemySystemConfigurationRepository(session),
    )


def _seed_user_with_two_allocations(session: Session) -> int:
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
    alpha = ProjectModel(
        name="Alpha Portal",
        description="First project",
        start_date=date(2026, 1, 1),
        manager_user_id=manager_id,
    )
    beta = ProjectModel(
        name="Beta CRM",
        description="Second project",
        start_date=date(2026, 1, 1),
        manager_user_id=manager_id,
    )
    session.add_all([alpha, beta])
    session.flush()
    session.add_all(
        [
            AllocationModel(
                user_id=user_id,
                project_id=alpha.id,
                utilisation_percent=50,
                from_date=date(2026, 1, 1),
                to_date=date(2026, 6, 30),
                status=AllocationStatus.ACTIVE,
                created_by_user_id=manager_id,
            ),
            AllocationModel(
                user_id=user_id,
                project_id=beta.id,
                utilisation_percent=50,
                from_date=date(2026, 1, 1),
                to_date=date(2026, 12, 31),
                status=AllocationStatus.ACTIVE,
                created_by_user_id=manager_id,
            ),
        ]
    )
    SqlAlchemySystemConfigurationRepository(session).create_with_defaults()
    session.flush()
    return user_id


def test_list_allocations_for_week_returns_expected_max_hours() -> None:
    with _session() as session:
        user_id = _seed_user_with_two_allocations(session)
        session.commit()
        service = _service(session)

        result = service.list_allocations_for_week(user_id, PAST_MONDAY)

        assert result.week_start_date == PAST_MONDAY
        assert result.max_weekly_hours == 40
        assert len(result.allocations) == 2
        assert result.allocations[0].project_name == "Alpha Portal"
        assert result.allocations[0].expected_max_hours == 20
        assert result.allocations[1].project_name == "Beta CRM"


def test_list_allocations_for_week_excludes_allocations_outside_week() -> None:
    with _session() as session:
        user_id = _seed_user_with_two_allocations(session)
        future_project = ProjectModel(
            name="Future Project",
            description="Starts after selected week",
            start_date=date(2026, 8, 1),
            manager_user_id=1,
        )
        session.add(future_project)
        session.flush()
        session.add(
            AllocationModel(
                user_id=user_id,
                project_id=future_project.id,
                utilisation_percent=25,
                from_date=date(2026, 8, 1),
                to_date=date(2026, 12, 31),
                status=AllocationStatus.ACTIVE,
                created_by_user_id=1,
            )
        )
        session.commit()
        service = _service(session)

        result = service.list_allocations_for_week(user_id, PAST_MONDAY)

        assert len(result.allocations) == 2
        assert all(row.project_name != "Future Project" for row in result.allocations)


def test_list_allocations_for_week_rejects_non_monday() -> None:
    with _session() as session:
        user_id = _seed_user_with_two_allocations(session)
        session.commit()
        service = _service(session)

        with pytest.raises(ValidationError, match="Monday"):
            service.list_allocations_for_week(user_id, date(2026, 5, 12))


def test_list_my_allocations_returns_active_rows_and_total() -> None:
    with _session() as session:
        user_id = _seed_user_with_two_allocations(session)
        session.commit()
        service = _service(session)

        result = service.list_my_allocations(user_id)

        assert len(result.allocations) == 2
        assert result.total_utilisation_percent == 100
        assert result.allocations[0].status == AllocationStatus.ACTIVE
        assert result.allocations[0].from_date == date(2026, 1, 1)


def test_list_my_allocations_raises_when_employee_profile_missing() -> None:
    with _session() as session:
        session.commit()
        service = _service(session)

        with pytest.raises(NotFoundError, match="Engineer profile"):
            service.list_my_allocations(999)
