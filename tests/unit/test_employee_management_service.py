"""Unit tests for EmployeeManagementService."""

from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from prm.application.employee_management_service import EmployeeManagementService
from prm.application.user_management_service import UserManagementService
from prm.domain.enums import AllocationStatus, EmployeeWorkStatus, Role, UserAccountStatus
from prm.domain.exceptions import NotFoundError, ValidationError
from prm.infrastructure.db.models import (
    AllocationModel,
    EmployeeModel,
    ProjectModel,
    UserModel,
)
from prm.infrastructure.db.repositories import (
    SqlAlchemyAllocationRepository,
    SqlAlchemyEmployeeRepository,
    SqlAlchemyUserRepository,
)
from prm.infrastructure.db.seed import seed_bootstrap_admin
from prm.infrastructure.security.password import BcryptPasswordHasher
from tests.unit.credentials import TEST_EMAIL, TEST_FULL_NAME, TEST_PASSWORD, TEST_USERNAME


def _session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    UserModel.__table__.create(engine, checkfirst=True)
    EmployeeModel.__table__.create(engine, checkfirst=True)
    ProjectModel.__table__.create(engine, checkfirst=True)
    AllocationModel.__table__.create(engine, checkfirst=True)
    return Session(engine)


def _service(session: Session) -> EmployeeManagementService:
    return EmployeeManagementService(
        employee_repository=SqlAlchemyEmployeeRepository(session),
        user_repository=SqlAlchemyUserRepository(session),
        allocation_repository=SqlAlchemyAllocationRepository(session),
    )


def _user_service(session: Session) -> UserManagementService:
    return UserManagementService(
        user_repository=SqlAlchemyUserRepository(session),
        password_hasher=BcryptPasswordHasher(),
    )


def _seed_admin(session: Session) -> None:
    seed_bootstrap_admin(
        session,
        username=TEST_USERNAME,
        password=TEST_PASSWORD,
        full_name=TEST_FULL_NAME,
        email=TEST_EMAIL,
    )


def _create_user(
    session: Session,
    *,
    username: str,
    email: str,
    role: Role,
) -> int:
    created = _user_service(session).create_user(
        full_name=f"{username} Name",
        email=email,
        username=username,
        temporary_password="TempPass1",
        role=role,
    )
    session.flush()
    return created.id


def test_create_employee_links_user_and_defaults_to_bench() -> None:
    with _session() as session:
        user_id = _create_user(
            session,
            username="ravi",
            email="ravi@example.test",
            role=Role.EMPLOYEE,
        )
        created = _service(session).create_employee(
            user_id=user_id,
            full_name="Ravi Kumar",
            email="ravi@example.test",
            department="Backend",
            designation="Senior Developer",
        )
        session.commit()

        assert created.user_id == user_id
        assert created.work_status == EmployeeWorkStatus.BENCH
        assert created.is_active is True


def test_create_employee_allows_manager_user() -> None:
    with _session() as session:
        user_id = _create_user(
            session,
            username="manager",
            email="manager@example.test",
            role=Role.MANAGER,
        )
        created = _service(session).create_employee(
            user_id=user_id,
            full_name="Manager Profile",
            email="manager@example.test",
            department="Delivery",
            designation="Delivery Manager",
        )
        session.commit()

        assert created.user_id == user_id


def test_create_employee_fails_when_user_missing() -> None:
    with _session() as session:
        with pytest.raises(NotFoundError):
            _service(session).create_employee(
                user_id=999,
                full_name="Missing User",
                email="missing@example.test",
                department="Backend",
                designation="Developer",
            )


def test_create_employee_fails_for_admin_user() -> None:
    with _session() as session:
        _seed_admin(session)
        with pytest.raises(ValidationError, match="Employee or Manager"):
            _service(session).create_employee(
                user_id=1,
                full_name="Admin Profile",
                email="admin-profile@example.test",
                department="IT",
                designation="Administrator",
            )


def test_create_employee_fails_when_profile_already_exists() -> None:
    with _session() as session:
        user_id = _create_user(
            session,
            username="ravi",
            email="ravi@example.test",
            role=Role.EMPLOYEE,
        )
        service = _service(session)
        service.create_employee(
            user_id=user_id,
            full_name="Ravi Kumar",
            email="ravi@example.test",
            department="Backend",
            designation="Developer",
        )
        session.commit()

        with pytest.raises(ValidationError, match="already has an employee profile"):
            service.create_employee(
                user_id=user_id,
                full_name="Duplicate",
                email="other@example.test",
                department="Backend",
                designation="Developer",
            )


def test_create_employee_fails_when_email_exists() -> None:
    with _session() as session:
        first_user = _create_user(
            session,
            username="first",
            email="first@example.test",
            role=Role.EMPLOYEE,
        )
        second_user = _create_user(
            session,
            username="second",
            email="second@example.test",
            role=Role.EMPLOYEE,
        )
        service = _service(session)
        service.create_employee(
            user_id=first_user,
            full_name="First Employee",
            email="shared@example.test",
            department="Backend",
            designation="Developer",
        )
        session.commit()

        with pytest.raises(ValidationError, match="Email"):
            service.create_employee(
                user_id=second_user,
                full_name="Second Employee",
                email="shared@example.test",
                department="Frontend",
                designation="Developer",
            )


def test_create_employee_fails_when_user_inactive() -> None:
    with _session() as session:
        _seed_admin(session)
        user_id = _create_user(
            session,
            username="inactive",
            email="inactive@example.test",
            role=Role.EMPLOYEE,
        )
        _user_service(session).deactivate_user(user_id, actor_user_id=1)
        session.commit()

        with pytest.raises(ValidationError, match="inactive user account"):
            _service(session).create_employee(
                user_id=user_id,
                full_name="Inactive User",
                email="inactive@example.test",
                department="Backend",
                designation="Developer",
            )


def test_list_employees_returns_summaries_and_counts() -> None:
    with _session() as session:
        bench_user = _create_user(
            session,
            username="bench",
            email="bench@example.test",
            role=Role.EMPLOYEE,
        )
        allocated_user = _create_user(
            session,
            username="allocated",
            email="allocated@example.test",
            role=Role.EMPLOYEE,
        )
        service = _service(session)
        bench_employee = service.create_employee(
            user_id=bench_user,
            full_name="Bench Employee",
            email="bench@example.test",
            department="Backend",
            designation="Developer",
        )
        allocated_employee = service.create_employee(
            user_id=allocated_user,
            full_name="Allocated Employee",
            email="allocated@example.test",
            department="Frontend",
            designation="Developer",
        )
        allocated_model = session.get(EmployeeModel, allocated_employee.id)
        assert allocated_model is not None
        allocated_model.work_status = EmployeeWorkStatus.ALLOCATED
        session.commit()

        result = service.list_employees()

        assert result.total == 2
        assert result.bench_count == 1
        assert result.allocated_count == 1
        assert result.employees[0].id == bench_employee.id
        assert result.employees[1].id == allocated_employee.id


def test_get_employee_returns_profile() -> None:
    with _session() as session:
        user_id = _create_user(
            session,
            username="ravi",
            email="ravi@example.test",
            role=Role.EMPLOYEE,
        )
        created = _service(session).create_employee(
            user_id=user_id,
            full_name="Ravi Kumar",
            email="ravi@example.test",
            department="Backend",
            designation="Developer",
        )
        session.commit()

        loaded = _service(session).get_employee(created.id)

        assert loaded.full_name == "Ravi Kumar"


def test_get_employee_fails_when_missing() -> None:
    with _session() as session:
        with pytest.raises(NotFoundError):
            _service(session).get_employee(999)


def test_update_employee_changes_fields() -> None:
    with _session() as session:
        user_id = _create_user(
            session,
            username="ravi",
            email="ravi@example.test",
            role=Role.EMPLOYEE,
        )
        created = _service(session).create_employee(
            user_id=user_id,
            full_name="Ravi Kumar",
            email="ravi@example.test",
            department="Backend",
            designation="Developer",
        )
        session.commit()

        updated = _service(session).update_employee(
            created.id,
            department="DevOps",
            designation="Lead Developer",
        )
        session.commit()

        assert updated.department == "DevOps"
        assert updated.designation == "Lead Developer"


def test_update_employee_fails_when_inactive() -> None:
    with _session() as session:
        user_id = _create_user(
            session,
            username="ravi",
            email="ravi@example.test",
            role=Role.EMPLOYEE,
        )
        service = _service(session)
        created = service.create_employee(
            user_id=user_id,
            full_name="Ravi Kumar",
            email="ravi@example.test",
            department="Backend",
            designation="Developer",
        )
        service.deactivate_employee(created.id)
        session.commit()

        with pytest.raises(ValidationError, match="inactive"):
            service.update_employee(created.id, department="DevOps")


def test_update_employee_fails_when_email_taken() -> None:
    with _session() as session:
        first_user = _create_user(
            session,
            username="first",
            email="first@example.test",
            role=Role.EMPLOYEE,
        )
        second_user = _create_user(
            session,
            username="second",
            email="second@example.test",
            role=Role.EMPLOYEE,
        )
        service = _service(session)
        service.create_employee(
            user_id=first_user,
            full_name="First Employee",
            email="first@example.test",
            department="Backend",
            designation="Developer",
        )
        second = service.create_employee(
            user_id=second_user,
            full_name="Second Employee",
            email="second@example.test",
            department="Frontend",
            designation="Developer",
        )
        session.commit()

        with pytest.raises(ValidationError, match="Email"):
            service.update_employee(second.id, email="first@example.test")


def test_deactivate_employee_sets_inactive_and_blocks_user() -> None:
    with _session() as session:
        user_id = _create_user(
            session,
            username="ravi",
            email="ravi@example.test",
            role=Role.EMPLOYEE,
        )
        service = _service(session)
        created = service.create_employee(
            user_id=user_id,
            full_name="Ravi Kumar",
            email="ravi@example.test",
            department="Backend",
            designation="Developer",
        )
        session.commit()

        deactivated = service.deactivate_employee(created.id)
        session.commit()

        user = SqlAlchemyUserRepository(session).find_by_id(user_id)
        assert deactivated.is_active is False
        assert user is not None
        assert user.account_status == UserAccountStatus.INACTIVE


def test_deactivate_employee_ends_active_allocations() -> None:
    with _session() as session:
        manager_id = _create_user(
            session,
            username="manager",
            email="manager@example.test",
            role=Role.MANAGER,
        )
        employee_user_id = _create_user(
            session,
            username="ravi",
            email="ravi@example.test",
            role=Role.EMPLOYEE,
        )
        service = _service(session)
        employee = service.create_employee(
            user_id=employee_user_id,
            full_name="Ravi Kumar",
            email="ravi@example.test",
            department="Backend",
            designation="Developer",
        )
        project = ProjectModel(
            name="Alpha Portal",
            description="Test project",
            start_date=date(2026, 1, 1),
            manager_user_id=manager_id,
        )
        session.add(project)
        session.flush()
        allocation = AllocationModel(
            employee_id=employee.id,
            project_id=project.id,
            utilisation_percent=50,
            from_date=date(2026, 6, 1),
            to_date=None,
            status=AllocationStatus.ACTIVE,
            created_by_user_id=manager_id,
        )
        session.add(allocation)
        session.commit()

        service.deactivate_employee(employee.id)
        session.commit()

        active = SqlAlchemyAllocationRepository(session).find_active_by_employee(employee.id)
        ended = session.get(AllocationModel, allocation.id)
        assert active == []
        assert ended is not None
        assert ended.status == AllocationStatus.ENDED
        assert ended.to_date == date.today()


def test_deactivate_employee_fails_when_already_inactive() -> None:
    with _session() as session:
        user_id = _create_user(
            session,
            username="ravi",
            email="ravi@example.test",
            role=Role.EMPLOYEE,
        )
        service = _service(session)
        created = service.create_employee(
            user_id=user_id,
            full_name="Ravi Kumar",
            email="ravi@example.test",
            department="Backend",
            designation="Developer",
        )
        service.deactivate_employee(created.id)
        session.commit()

        with pytest.raises(ValidationError, match="already inactive"):
            service.deactivate_employee(created.id)


def test_deactivate_employee_fails_when_missing() -> None:
    with _session() as session:
        with pytest.raises(NotFoundError):
            _service(session).deactivate_employee(999)


def test_assign_manager_links_employee_to_manager_user() -> None:
    with _session() as session:
        manager_user_id = _create_user(
            session,
            username="ankit",
            email="ankit@example.test",
            role=Role.MANAGER,
        )
        employee_user_id = _create_user(
            session,
            username="ravi",
            email="ravi@example.test",
            role=Role.EMPLOYEE,
        )
        service = _service(session)
        service.create_employee(
            user_id=employee_user_id,
            full_name="Ravi Kumar",
            email="ravi@example.test",
            department="Backend",
            designation="Developer",
        )
        session.commit()

        updated = service.assign_manager(
            employee_user_id=employee_user_id,
            manager_user_id=manager_user_id,
        )
        session.commit()

        assert updated.manager_id == manager_user_id


def test_assign_manager_fails_when_employee_profile_missing() -> None:
    with _session() as session:
        manager_user_id = _create_user(
            session,
            username="ankit",
            email="ankit@example.test",
            role=Role.MANAGER,
        )
        employee_user_id = _create_user(
            session,
            username="ravi",
            email="ravi@example.test",
            role=Role.EMPLOYEE,
        )
        session.commit()

        with pytest.raises(NotFoundError, match="No employee profile found"):
            _service(session).assign_manager(
                employee_user_id=employee_user_id,
                manager_user_id=manager_user_id,
            )


def test_assign_manager_fails_when_manager_is_not_manager_role() -> None:
    with _session() as session:
        employee_user_id = _create_user(
            session,
            username="ravi",
            email="ravi@example.test",
            role=Role.EMPLOYEE,
        )
        other_employee_user_id = _create_user(
            session,
            username="priya",
            email="priya@example.test",
            role=Role.EMPLOYEE,
        )
        service = _service(session)
        service.create_employee(
            user_id=employee_user_id,
            full_name="Ravi Kumar",
            email="ravi@example.test",
            department="Backend",
            designation="Developer",
        )
        session.commit()

        with pytest.raises(ValidationError, match="MANAGER role"):
            service.assign_manager(
                employee_user_id=employee_user_id,
                manager_user_id=other_employee_user_id,
            )


def test_assign_manager_fails_when_self_assignment() -> None:
    with _session() as session:
        manager_user_id = _create_user(
            session,
            username="ankit",
            email="ankit@example.test",
            role=Role.MANAGER,
        )
        service = _service(session)
        service.create_employee(
            user_id=manager_user_id,
            full_name="Ankit Shah",
            email="ankit@example.test",
            department="Delivery",
            designation="Delivery Manager",
        )
        session.commit()

        with pytest.raises(ValidationError, match="own manager"):
            service.assign_manager(
                employee_user_id=manager_user_id,
                manager_user_id=manager_user_id,
            )
