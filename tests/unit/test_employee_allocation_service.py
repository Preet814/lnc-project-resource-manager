"""Unit tests for EmployeeAllocationService."""

from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from prm.application.employee_allocation_service import EmployeeAllocationService
from prm.domain.enums import AllocationStatus, Role
from prm.domain.exceptions import NotFoundError, ValidationError
from prm.infrastructure.db.models import (
    AllocationModel,
    EmployeeModel,
    ProjectModel,
    SystemConfigurationModel,
    UserModel,
)
from prm.infrastructure.db.repositories import (
    SqlAlchemyAllocationRepository,
    SqlAlchemyEmployeeRepository,
    SqlAlchemyProjectRepository,
    SqlAlchemySystemConfigurationRepository,
    SqlAlchemyUserRepository,
)
from prm.infrastructure.security.password import BcryptPasswordHasher

PAST_MONDAY = date(2026, 5, 11)


def _session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    UserModel.__table__.create(engine, checkfirst=True)
    EmployeeModel.__table__.create(engine, checkfirst=True)
    ProjectModel.__table__.create(engine, checkfirst=True)
    AllocationModel.__table__.create(engine, checkfirst=True)
    SystemConfigurationModel.__table__.create(engine, checkfirst=True)
    return Session(engine)


def _service(session: Session) -> EmployeeAllocationService:
    return EmployeeAllocationService(
        employee_repository=SqlAlchemyEmployeeRepository(session),
        allocation_repository=SqlAlchemyAllocationRepository(session),
        project_repository=SqlAlchemyProjectRepository(session),
        config_repository=SqlAlchemySystemConfigurationRepository(session),
    )


def _seed_employee_with_two_allocations(
    session: Session,
) -> tuple[int, int]:
    """Return (user_id, employee_id)."""
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
    alpha = ProjectModel(
        name="Alpha Portal",
        description="First project",
        start_date=date(2026, 1, 1),
        manager_user_id=manager.id,
    )
    beta = ProjectModel(
        name="Beta CRM",
        description="Second project",
        start_date=date(2026, 1, 1),
        manager_user_id=manager.id,
    )
    session.add_all([alpha, beta])
    session.flush()
    session.add_all(
        [
            AllocationModel(
                employee_id=employee.id,
                project_id=alpha.id,
                utilisation_percent=50,
                from_date=date(2026, 1, 1),
                to_date=date(2026, 6, 30),
                status=AllocationStatus.ACTIVE,
                created_by_user_id=manager.id,
            ),
            AllocationModel(
                employee_id=employee.id,
                project_id=beta.id,
                utilisation_percent=50,
                from_date=date(2026, 1, 1),
                to_date=date(2026, 12, 31),
                status=AllocationStatus.ACTIVE,
                created_by_user_id=manager.id,
            ),
        ]
    )
    SqlAlchemySystemConfigurationRepository(session).create_with_defaults()
    session.flush()
    return employee_user.id, employee.id


def test_list_allocations_for_week_returns_expected_max_hours() -> None:
    with _session() as session:
        user_id, _employee_id = _seed_employee_with_two_allocations(session)
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
        user_id, employee_id = _seed_employee_with_two_allocations(session)
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
                employee_id=employee_id,
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
        user_id, _employee_id = _seed_employee_with_two_allocations(session)
        session.commit()
        service = _service(session)

        with pytest.raises(ValidationError, match="Monday"):
            service.list_allocations_for_week(user_id, date(2026, 5, 12))


def test_list_my_allocations_returns_active_rows_and_total() -> None:
    with _session() as session:
        user_id, _employee_id = _seed_employee_with_two_allocations(session)
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

        with pytest.raises(NotFoundError, match="Employee profile"):
            service.list_my_allocations(999)
