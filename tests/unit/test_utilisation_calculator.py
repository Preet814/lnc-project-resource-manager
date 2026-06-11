"""Unit tests for UtilisationCalculator."""

from datetime import date

from sqlalchemy.orm import Session

from prm.application.utilisation_calculator import UtilisationCalculator
from prm.domain.constants import MAX_UTILISATION_PERCENT
from prm.domain.enums import AllocationStatus, Role
from prm.infrastructure.db.models import AllocationModel, ProjectModel
from prm.infrastructure.db.repositories import SqlAlchemyAllocationRepository
from tests.unit.engineer_fixtures import (
    create_allocation_tables,
    create_memory_session,
    create_user,
    seed_rbac,
)


def _session() -> Session:
    session = create_memory_session(include_project=True)
    create_allocation_tables(session)
    return session


def _calculator(session: Session) -> UtilisationCalculator:
    return UtilisationCalculator(SqlAlchemyAllocationRepository(session))


def _seed_user_and_project(session: Session) -> tuple[int, int, int]:
    seed_rbac(session)
    manager_id = create_user(
        session,
        username="manager",
        email="manager@example.test",
        full_name="Manager User",
        role=Role.MANAGER,
    )
    user_id = create_user(
        session,
        username="employee",
        email="employee@example.test",
        full_name="Ravi Kumar",
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
    return manager_id, user_id, project.id


def test_validate_new_allocation_passes_when_under_cap() -> None:
    with _session() as session:
        manager_id, user_id, project_id = _seed_user_and_project(session)
        session.add(
            AllocationModel(
                user_id=user_id,
                project_id=project_id,
                utilisation_percent=50,
                from_date=date(2026, 3, 1),
                to_date=date(2026, 5, 31),
                status=AllocationStatus.ACTIVE,
                created_by_user_id=manager_id,
            )
        )
        session.commit()
        calculator = _calculator(session)

        result = calculator.validate_new_allocation(
            user_id,
            50,
            date(2026, 6, 1),
            date(2026, 9, 30),
        )

        assert result.is_valid is True
        assert result.total_percent == 50


def test_validate_new_allocation_sums_overlapping_allocations() -> None:
    with _session() as session:
        manager_id, user_id, project_id = _seed_user_and_project(session)
        session.add(
            AllocationModel(
                user_id=user_id,
                project_id=project_id,
                utilisation_percent=50,
                from_date=date(2026, 3, 1),
                to_date=date(2026, 8, 31),
                status=AllocationStatus.ACTIVE,
                created_by_user_id=manager_id,
            )
        )
        session.commit()
        calculator = _calculator(session)

        result = calculator.validate_new_allocation(
            user_id,
            50,
            date(2026, 6, 1),
            date(2026, 9, 30),
        )

        assert result.is_valid is True
        assert result.total_percent == 100


def test_validate_new_allocation_fails_when_over_cap() -> None:
    with _session() as session:
        manager_id, user_id, project_id = _seed_user_and_project(session)
        session.add(
            AllocationModel(
                user_id=user_id,
                project_id=project_id,
                utilisation_percent=75,
                from_date=date(2026, 3, 1),
                to_date=date(2026, 8, 31),
                status=AllocationStatus.ACTIVE,
                created_by_user_id=manager_id,
            )
        )
        session.commit()
        calculator = _calculator(session)

        result = calculator.validate_new_allocation(
            user_id,
            50,
            date(2026, 6, 1),
            date(2026, 9, 30),
        )

        assert result.is_valid is False
        assert result.total_percent == 125
        assert "125%" in result.message


def test_validate_new_allocation_rejects_invalid_date_range() -> None:
    with _session() as session:
        _, user_id, _ = _seed_user_and_project(session)
        session.commit()
        calculator = _calculator(session)

        result = calculator.validate_new_allocation(
            user_id,
            50,
            date(2026, 9, 30),
            date(2026, 6, 1),
        )

        assert result.is_valid is False
        assert "From date" in result.message


def test_validate_new_allocation_rejects_invalid_percent() -> None:
    with _session() as session:
        _, user_id, _ = _seed_user_and_project(session)
        session.commit()
        calculator = _calculator(session)

        result = calculator.validate_new_allocation(
            user_id,
            MAX_UTILISATION_PERCENT + 1,
            date(2026, 6, 1),
            date(2026, 9, 30),
        )

        assert result.is_valid is False
        assert "Utilisation must be between" in result.message


def test_compute_utilisation_on_sums_active_allocations_for_date() -> None:
    with _session() as session:
        manager_id, user_id, project_id = _seed_user_and_project(session)
        session.add(
            AllocationModel(
                user_id=user_id,
                project_id=project_id,
                utilisation_percent=50,
                from_date=date(2026, 3, 1),
                to_date=date(2026, 6, 30),
                status=AllocationStatus.ACTIVE,
                created_by_user_id=manager_id,
            )
        )
        session.add(
            AllocationModel(
                user_id=user_id,
                project_id=project_id,
                utilisation_percent=50,
                from_date=date(2026, 4, 1),
                to_date=date(2026, 7, 31),
                status=AllocationStatus.ACTIVE,
                created_by_user_id=manager_id,
            )
        )
        session.commit()
        calculator = _calculator(session)

        assert calculator.compute_utilisation_on(user_id, date(2026, 5, 1)) == 100
        assert calculator.compute_utilisation_on(user_id, date(2026, 8, 1)) == 0
