"""Unit tests for AllocationService."""

from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from prm.application.allocation_service import AllocationService
from prm.application.authorization_service import AuthorizationService
from prm.application.utilisation_calculator import UtilisationCalculator
from prm.domain.enums import AllocationStatus, EmployeeWorkStatus, ProjectStatus, Role
from prm.domain.exceptions import ConflictError, NotFoundError, UnauthorizedError, ValidationError
from prm.infrastructure.db.models import (
    AllocationModel,
    EmployeeModel,
    ProjectModel,
    UserModel,
)
from prm.infrastructure.db.repositories import (
    SqlAlchemyAllocationRepository,
    SqlAlchemyEmployeeRepository,
    SqlAlchemyProjectRepository,
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


def _service(session: Session) -> AllocationService:
    project_repo = SqlAlchemyProjectRepository(session)
    return AllocationService(
        allocation_repository=SqlAlchemyAllocationRepository(session),
        employee_repository=SqlAlchemyEmployeeRepository(session),
        project_repository=project_repo,
        authorization=AuthorizationService(project_repo),
        utilisation=UtilisationCalculator(SqlAlchemyAllocationRepository(session)),
    )


def _seed(
    session: Session,
    *,
    project_status: ProjectStatus = ProjectStatus.ACTIVE,
    manager_user_id: int | None = None,
) -> tuple[int, int, int]:
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
    owner_id = manager_user_id or manager.id
    project = ProjectModel(
        name="Alpha Portal",
        description="Test project",
        start_date=date(2026, 1, 1),
        status=project_status,
        manager_user_id=owner_id,
    )
    session.add(project)
    session.flush()
    return owner_id, employee.id, project.id


def test_allocate_direct_creates_allocation_and_updates_employee() -> None:
    with _session() as session:
        manager_id, employee_id, project_id = _seed(session)
        session.commit()
        service = _service(session)

        allocation = service.allocate_direct(
            manager_id,
            project_id=project_id,
            employee_id=employee_id,
            utilisation_percent=50,
            from_date=date(2026, 6, 1),
            to_date=date(2026, 9, 30),
        )
        session.commit()

        assert allocation.status == AllocationStatus.ACTIVE
        assert allocation.utilisation_percent == 50
        employee = SqlAlchemyEmployeeRepository(session).find_by_id(employee_id)
        assert employee is not None
        assert employee.current_utilisation_percent == 50
        assert employee.work_status == EmployeeWorkStatus.ALLOCATED


def test_allocate_direct_raises_conflict_when_over_cap() -> None:
    with _session() as session:
        manager_id, employee_id, project_id = _seed(session)
        session.add(
            AllocationModel(
                employee_id=employee_id,
                project_id=project_id,
                utilisation_percent=75,
                from_date=date(2026, 3, 1),
                to_date=date(2026, 8, 31),
                status=AllocationStatus.ACTIVE,
                created_by_user_id=manager_id,
            )
        )
        session.commit()
        service = _service(session)

        with pytest.raises(ConflictError, match="125%"):
            service.allocate_direct(
                manager_id,
                project_id=project_id,
                employee_id=employee_id,
                utilisation_percent=50,
                from_date=date(2026, 6, 1),
                to_date=date(2026, 9, 30),
            )


def test_allocate_direct_raises_when_project_not_allocatable() -> None:
    with _session() as session:
        manager_id, employee_id, project_id = _seed(
            session,
            project_status=ProjectStatus.ON_HOLD,
        )
        session.commit()
        service = _service(session)

        with pytest.raises(ValidationError, match="ACTIVE or PLANNED"):
            service.allocate_direct(
                manager_id,
                project_id=project_id,
                employee_id=employee_id,
                utilisation_percent=50,
                from_date=date(2026, 6, 1),
                to_date=date(2026, 9, 30),
            )


def test_allocate_direct_raises_when_not_project_owner() -> None:
    with _session() as session:
        manager_id, employee_id, project_id = _seed(session)
        user_repo = SqlAlchemyUserRepository(session)
        hasher = BcryptPasswordHasher()
        outsider = user_repo.create(
            full_name="Outsider",
            username="outsider",
            email="outsider@example.test",
            password_hash=hasher.hash("TempPass1"),
            role=Role.MANAGER,
        )
        session.commit()
        service = _service(session)

        with pytest.raises(UnauthorizedError, match="project owner"):
            service.allocate_direct(
                outsider.id,
                project_id=project_id,
                employee_id=employee_id,
                utilisation_percent=50,
                from_date=date(2026, 6, 1),
                to_date=date(2026, 9, 30),
            )


def test_end_allocation_sets_ended_and_returns_employee_to_bench() -> None:
    with _session() as session:
        manager_id, employee_id, project_id = _seed(session)
        allocation = AllocationModel(
            employee_id=employee_id,
            project_id=project_id,
            utilisation_percent=50,
            from_date=date(2026, 3, 1),
            to_date=date(2026, 8, 31),
            status=AllocationStatus.ACTIVE,
            created_by_user_id=manager_id,
        )
        session.add(allocation)
        session.flush()
        employee_repo = SqlAlchemyEmployeeRepository(session)
        employee_repo.update_utilisation_and_status(
            employee_id,
            current_utilisation_percent=50,
            work_status=EmployeeWorkStatus.ALLOCATED,
        )
        session.commit()
        service = _service(session)
        end_date = date(2026, 6, 14)

        ended = service.end_allocation(
            manager_id,
            allocation.id,
            as_of=end_date,
        )
        session.commit()

        assert ended.status == AllocationStatus.ENDED
        assert ended.to_date == end_date
        employee = employee_repo.find_by_id(employee_id)
        assert employee is not None
        assert employee.work_status == EmployeeWorkStatus.BENCH
        assert employee.current_utilisation_percent == 0


def test_list_project_allocations_returns_active_rows_for_owner() -> None:
    with _session() as session:
        manager_id, employee_id, project_id = _seed(session)
        session.add(
            AllocationModel(
                employee_id=employee_id,
                project_id=project_id,
                utilisation_percent=50,
                from_date=date(2026, 3, 1),
                to_date=date(2026, 8, 31),
                status=AllocationStatus.ACTIVE,
                created_by_user_id=manager_id,
            )
        )
        session.commit()
        service = _service(session)

        allocations = service.list_project_allocations(manager_id, project_id)

        assert len(allocations) == 1
        assert allocations[0].employee_full_name == "Ravi Kumar"
        assert allocations[0].project_name == "Alpha Portal"


def test_end_allocation_raises_when_allocation_missing() -> None:
    with _session() as session:
        manager_id, _, _ = _seed(session)
        session.commit()
        service = _service(session)

        with pytest.raises(NotFoundError, match="Allocation 999 not found"):
            service.end_allocation(manager_id, 999)
