"""Unit tests for UtilisationCalculator."""

from datetime import date

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from prm.application.utilisation_calculator import UtilisationCalculator
from prm.domain.constants import MAX_UTILISATION_PERCENT
from prm.domain.enums import AllocationStatus, Role
from prm.infrastructure.db.models import AllocationModel, EmployeeModel, ProjectModel, UserModel
from prm.infrastructure.db.repositories import (
    SqlAlchemyAllocationRepository,
    SqlAlchemyEmployeeRepository,
    SqlAlchemyUserRepository,
)
from prm.infrastructure.security.password import BcryptPasswordHasher


def _session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    UserModel.__table__.create(engine, checkfirst=True)
    EmployeeModel.__table__.create(engine, checkfirst=True)
    ProjectModel.__table__.create(engine, checkfirst=True)
    AllocationModel.__table__.create(engine, checkfirst=True)
    return Session(engine)


def _calculator(session: Session) -> UtilisationCalculator:
    return UtilisationCalculator(SqlAlchemyAllocationRepository(session))


def _seed_employee_and_project(session: Session) -> tuple[int, int, int]:
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
    employee_repo = SqlAlchemyEmployeeRepository(session)
    employee = employee_repo.create(
        user_id=employee_user.id,
        full_name="Ravi Kumar",
        email="employee@example.test",
        department="Backend",
        designation="Developer",
    )
    project = ProjectModel(
        name="Alpha Portal",
        description="Test project",
        start_date=date(2026, 1, 1),
        manager_user_id=manager.id,
    )
    session.add(project)
    session.flush()
    return manager.id, employee.id, project.id


def test_validate_new_allocation_passes_when_under_cap() -> None:
    with _session() as session:
        _, employee_id, project_id = _seed_employee_and_project(session)
        session.add(
            AllocationModel(
                employee_id=employee_id,
                project_id=project_id,
                utilisation_percent=50,
                from_date=date(2026, 3, 1),
                to_date=date(2026, 5, 31),
                status=AllocationStatus.ACTIVE,
                created_by_user_id=1,
            )
        )
        session.commit()
        calculator = _calculator(session)

        result = calculator.validate_new_allocation(
            employee_id,
            50,
            date(2026, 6, 1),
            date(2026, 9, 30),
        )

        assert result.is_valid is True
        assert result.total_percent == 50


def test_validate_new_allocation_sums_overlapping_allocations() -> None:
    with _session() as session:
        _, employee_id, project_id = _seed_employee_and_project(session)
        session.add(
            AllocationModel(
                employee_id=employee_id,
                project_id=project_id,
                utilisation_percent=50,
                from_date=date(2026, 3, 1),
                to_date=date(2026, 8, 31),
                status=AllocationStatus.ACTIVE,
                created_by_user_id=1,
            )
        )
        session.commit()
        calculator = _calculator(session)

        result = calculator.validate_new_allocation(
            employee_id,
            50,
            date(2026, 6, 1),
            date(2026, 9, 30),
        )

        assert result.is_valid is True
        assert result.total_percent == 100


def test_validate_new_allocation_fails_when_over_cap() -> None:
    with _session() as session:
        _, employee_id, project_id = _seed_employee_and_project(session)
        session.add(
            AllocationModel(
                employee_id=employee_id,
                project_id=project_id,
                utilisation_percent=75,
                from_date=date(2026, 3, 1),
                to_date=date(2026, 8, 31),
                status=AllocationStatus.ACTIVE,
                created_by_user_id=1,
            )
        )
        session.commit()
        calculator = _calculator(session)

        result = calculator.validate_new_allocation(
            employee_id,
            50,
            date(2026, 6, 1),
            date(2026, 9, 30),
        )

        assert result.is_valid is False
        assert result.total_percent == 125
        assert "125%" in result.message


def test_validate_new_allocation_rejects_invalid_date_range() -> None:
    with _session() as session:
        _, employee_id, _ = _seed_employee_and_project(session)
        session.commit()
        calculator = _calculator(session)

        result = calculator.validate_new_allocation(
            employee_id,
            50,
            date(2026, 9, 30),
            date(2026, 6, 1),
        )

        assert result.is_valid is False
        assert "From date" in result.message


def test_validate_new_allocation_rejects_invalid_percent() -> None:
    with _session() as session:
        _, employee_id, _ = _seed_employee_and_project(session)
        session.commit()
        calculator = _calculator(session)

        result = calculator.validate_new_allocation(
            employee_id,
            MAX_UTILISATION_PERCENT + 1,
            date(2026, 6, 1),
            date(2026, 9, 30),
        )

        assert result.is_valid is False
        assert "Utilisation must be between" in result.message


def test_compute_utilisation_on_sums_active_allocations_for_date() -> None:
    with _session() as session:
        _, employee_id, project_id = _seed_employee_and_project(session)
        session.add(
            AllocationModel(
                employee_id=employee_id,
                project_id=project_id,
                utilisation_percent=50,
                from_date=date(2026, 3, 1),
                to_date=date(2026, 6, 30),
                status=AllocationStatus.ACTIVE,
                created_by_user_id=1,
            )
        )
        session.add(
            AllocationModel(
                employee_id=employee_id,
                project_id=project_id,
                utilisation_percent=50,
                from_date=date(2026, 4, 1),
                to_date=date(2026, 7, 31),
                status=AllocationStatus.ACTIVE,
                created_by_user_id=1,
            )
        )
        session.commit()
        calculator = _calculator(session)

        assert calculator.compute_utilisation_on(employee_id, date(2026, 5, 1)) == 100
        assert calculator.compute_utilisation_on(employee_id, date(2026, 8, 1)) == 0
