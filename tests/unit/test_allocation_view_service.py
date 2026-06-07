"""Unit tests for AllocationViewService."""

from datetime import date

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from prm.application.allocation_view_service import AllocationViewService
from prm.application.employee_management_service import EmployeeManagementService
from prm.application.project_management_service import ProjectManagementService
from prm.application.user_management_service import UserManagementService
from prm.domain.enums import AllocationStatus, ProjectStatus, Role
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


def _service(session: Session) -> AllocationViewService:
    return AllocationViewService(
        allocation_repository=SqlAlchemyAllocationRepository(session),
        employee_repository=SqlAlchemyEmployeeRepository(session),
        project_repository=SqlAlchemyProjectRepository(session),
    )


def _user_service(session: Session) -> UserManagementService:
    return UserManagementService(
        user_repository=SqlAlchemyUserRepository(session),
        password_hasher=BcryptPasswordHasher(),
    )


def _employee_service(session: Session) -> EmployeeManagementService:
    return EmployeeManagementService(
        employee_repository=SqlAlchemyEmployeeRepository(session),
        user_repository=SqlAlchemyUserRepository(session),
        allocation_repository=SqlAlchemyAllocationRepository(session),
    )


def _project_service(session: Session) -> ProjectManagementService:
    return ProjectManagementService(
        project_repository=SqlAlchemyProjectRepository(session),
        user_repository=SqlAlchemyUserRepository(session),
    )


def _create_user(
    session: Session,
    *,
    username: str,
    email: str,
    role: Role,
    full_name: str,
) -> int:
    created = _user_service(session).create_user(
        full_name=full_name,
        email=email,
        username=username,
        temporary_password="TempPass1",
        role=role,
    )
    session.flush()
    return created.id


def _create_employee(
    session: Session,
    *,
    username: str,
    email: str,
    full_name: str,
    department: str = "Backend",
) -> int:
    user_id = _create_user(
        session,
        username=username,
        email=email,
        role=Role.EMPLOYEE,
        full_name=full_name,
    )
    employee = _employee_service(session).create_employee(
        user_id=user_id,
        full_name=full_name,
        email=email,
        department=department,
        designation="Developer",
    )
    session.flush()
    return employee.id


def _create_project(session: Session, *, manager_user_id: int, name: str) -> int:
    project = _project_service(session).create_project(
        name=name,
        description=None,
        start_date=date(2026, 3, 1),
        end_date=date(2026, 6, 30),
        status=ProjectStatus.ACTIVE,
        manager_user_id=manager_user_id,
    )
    session.flush()
    return project.id


def _create_allocation(
    session: Session,
    *,
    employee_id: int,
    project_id: int,
    created_by_user_id: int,
    utilisation_percent: int = 50,
    status: AllocationStatus = AllocationStatus.ACTIVE,
) -> int:
    allocation = AllocationModel(
        employee_id=employee_id,
        project_id=project_id,
        utilisation_percent=utilisation_percent,
        from_date=date(2026, 3, 1),
        to_date=date(2026, 6, 30),
        status=status,
        created_by_user_id=created_by_user_id,
    )
    session.add(allocation)
    session.flush()
    return allocation.id


def test_list_allocations_returns_enriched_summaries() -> None:
    with _session() as session:
        manager_id = _create_user(
            session,
            username="ankit",
            email="ankit@example.test",
            role=Role.MANAGER,
            full_name="Ankit Shah",
        )
        ravi_id = _create_employee(
            session,
            username="ravi",
            email="ravi@example.test",
            full_name="Ravi Kumar",
        )
        neha_id = _create_employee(
            session,
            username="neha",
            email="neha@example.test",
            full_name="Neha Joshi",
            department="Frontend",
        )
        alpha_id = _create_project(session, manager_user_id=manager_id, name="Alpha Portal")
        beta_id = _create_project(session, manager_user_id=manager_id, name="Beta CRM")
        _create_allocation(
            session,
            employee_id=ravi_id,
            project_id=alpha_id,
            created_by_user_id=manager_id,
        )
        _create_allocation(
            session,
            employee_id=ravi_id,
            project_id=beta_id,
            created_by_user_id=manager_id,
        )
        _create_allocation(
            session,
            employee_id=neha_id,
            project_id=alpha_id,
            created_by_user_id=manager_id,
            utilisation_percent=100,
        )
        session.commit()

        result = _service(session).list_allocations()

        assert result.total == 3
        assert len(result.allocations) == 3
        first = result.allocations[0]
        assert first.employee_full_name == "Ravi Kumar"
        assert first.project_name == "Alpha Portal"
        assert first.utilisation_percent == 50
        assert first.from_date == date(2026, 3, 1)
        assert first.to_date == date(2026, 6, 30)


def test_list_allocations_filters_by_employee_id() -> None:
    with _session() as session:
        manager_id = _create_user(
            session,
            username="ankit",
            email="ankit@example.test",
            role=Role.MANAGER,
            full_name="Ankit Shah",
        )
        ravi_id = _create_employee(
            session,
            username="ravi",
            email="ravi@example.test",
            full_name="Ravi Kumar",
        )
        neha_id = _create_employee(
            session,
            username="neha",
            email="neha@example.test",
            full_name="Neha Joshi",
        )
        project_id = _create_project(session, manager_user_id=manager_id, name="Alpha Portal")
        _create_allocation(
            session,
            employee_id=ravi_id,
            project_id=project_id,
            created_by_user_id=manager_id,
        )
        _create_allocation(
            session,
            employee_id=neha_id,
            project_id=project_id,
            created_by_user_id=manager_id,
        )
        session.commit()

        result = _service(session).list_allocations(employee_id=ravi_id)

        assert result.total == 1
        assert result.allocations[0].employee_full_name == "Ravi Kumar"
        assert result.allocations[0].employee_id == ravi_id


def test_list_allocations_filters_by_project_id() -> None:
    with _session() as session:
        manager_id = _create_user(
            session,
            username="ankit",
            email="ankit@example.test",
            role=Role.MANAGER,
            full_name="Ankit Shah",
        )
        employee_id = _create_employee(
            session,
            username="ravi",
            email="ravi@example.test",
            full_name="Ravi Kumar",
        )
        alpha_id = _create_project(session, manager_user_id=manager_id, name="Alpha Portal")
        beta_id = _create_project(session, manager_user_id=manager_id, name="Beta CRM")
        _create_allocation(
            session,
            employee_id=employee_id,
            project_id=alpha_id,
            created_by_user_id=manager_id,
        )
        _create_allocation(
            session,
            employee_id=employee_id,
            project_id=beta_id,
            created_by_user_id=manager_id,
        )
        session.commit()

        result = _service(session).list_allocations(project_id=alpha_id)

        assert result.total == 1
        assert result.allocations[0].project_name == "Alpha Portal"
        assert result.allocations[0].project_id == alpha_id


def test_list_allocations_returns_empty_when_none() -> None:
    with _session() as session:
        session.commit()

        result = _service(session).list_allocations()

        assert result.total == 0
        assert result.allocations == ()
