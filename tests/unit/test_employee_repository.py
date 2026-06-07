"""Unit tests for SQLAlchemy employee repository."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from prm.domain.enums import EmployeeWorkStatus, Role
from prm.domain.exceptions import NotFoundError
from prm.infrastructure.db.models import EmployeeModel, UserModel
from prm.infrastructure.db.repositories import (
    SqlAlchemyEmployeeRepository,
    SqlAlchemyUserRepository,
)
from prm.infrastructure.security.password import BcryptPasswordHasher


def _session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    UserModel.__table__.create(engine, checkfirst=True)
    EmployeeModel.__table__.create(engine, checkfirst=True)
    return Session(engine)


def _create_user(session: Session, *, username: str, email: str) -> int:
    repo = SqlAlchemyUserRepository(session)
    hasher = BcryptPasswordHasher()
    user = repo.create(
        full_name=f"{username} Name",
        username=username,
        email=email,
        password_hash=hasher.hash("TempPass1"),
        role=Role.EMPLOYEE,
    )
    session.flush()
    return user.id


def _create_employee(
    session: Session,
    *,
    user_id: int,
    email: str,
    department: str = "Backend",
    designation: str = "Developer",
) -> int:
    repo = SqlAlchemyEmployeeRepository(session)
    employee = repo.create(
        user_id=user_id,
        full_name="Ravi Kumar",
        email=email,
        department=department,
        designation=designation,
    )
    session.flush()
    return employee.id


def test_create_persists_employee_with_bench_status() -> None:
    with _session() as session:
        user_id = _create_user(session, username="ravi", email="ravi@example.test")
        repo = SqlAlchemyEmployeeRepository(session)

        created = repo.create(
            user_id=user_id,
            full_name="Ravi Kumar",
            email="ravi@example.test",
            department="Backend",
            designation="Senior Developer",
        )
        session.commit()

        assert created.work_status == EmployeeWorkStatus.BENCH
        assert created.is_active is True
        assert created.user_id == user_id
        assert created.current_utilisation_percent == 0


def test_find_by_id_returns_domain_employee() -> None:
    with _session() as session:
        user_id = _create_user(session, username="ravi", email="ravi@example.test")
        employee_id = _create_employee(session, user_id=user_id, email="ravi@example.test")
        repo = SqlAlchemyEmployeeRepository(session)

        employee = repo.find_by_id(employee_id)

        assert employee is not None
        assert employee.id == employee_id
        assert employee.email == "ravi@example.test"


def test_find_by_user_id_returns_domain_employee() -> None:
    with _session() as session:
        user_id = _create_user(session, username="ravi", email="ravi@example.test")
        _create_employee(session, user_id=user_id, email="ravi@example.test")
        repo = SqlAlchemyEmployeeRepository(session)

        employee = repo.find_by_user_id(user_id)

        assert employee is not None
        assert employee.user_id == user_id


def test_find_by_email_returns_domain_employee() -> None:
    with _session() as session:
        user_id = _create_user(session, username="ravi", email="ravi@example.test")
        _create_employee(session, user_id=user_id, email="ravi@example.test")
        repo = SqlAlchemyEmployeeRepository(session)

        employee = repo.find_by_email("ravi@example.test")

        assert employee is not None
        assert employee.full_name == "Ravi Kumar"


def test_find_returns_none_when_missing() -> None:
    with _session() as session:
        repo = SqlAlchemyEmployeeRepository(session)

        assert repo.find_by_id(999) is None
        assert repo.find_by_user_id(999) is None
        assert repo.find_by_email("missing@example.test") is None


def test_list_all_returns_employees_ordered_by_id() -> None:
    with _session() as session:
        first_user = _create_user(session, username="first", email="first@example.test")
        second_user = _create_user(session, username="second", email="second@example.test")
        repo = SqlAlchemyEmployeeRepository(session)
        first_id = repo.create(
            user_id=first_user,
            full_name="First Employee",
            email="first@example.test",
            department="Backend",
            designation="Developer",
        ).id
        second_id = repo.create(
            user_id=second_user,
            full_name="Second Employee",
            email="second@example.test",
            department="Frontend",
            designation="Developer",
        ).id
        session.commit()

        employees = repo.list_all()

        assert len(employees) == 2
        assert employees[0].id == first_id
        assert employees[1].id == second_id


def test_list_all_filters_by_work_status_and_department() -> None:
    with _session() as session:
        bench_user = _create_user(session, username="bench", email="bench@example.test")
        allocated_user = _create_user(session, username="alloc", email="alloc@example.test")
        repo = SqlAlchemyEmployeeRepository(session)
        bench_employee = repo.create(
            user_id=bench_user,
            full_name="Bench Employee",
            email="bench@example.test",
            department="Backend",
            designation="Developer",
        )
        allocated_employee = repo.create(
            user_id=allocated_user,
            full_name="Allocated Employee",
            email="alloc@example.test",
            department="Frontend",
            designation="Developer",
        )
        allocated_model = session.get(EmployeeModel, allocated_employee.id)
        assert allocated_model is not None
        allocated_model.work_status = EmployeeWorkStatus.ALLOCATED
        session.commit()

        by_status = repo.list_all(work_status=EmployeeWorkStatus.BENCH)
        by_department = repo.list_all(department="Frontend")

        assert len(by_status) == 1
        assert by_status[0].id == bench_employee.id
        assert len(by_department) == 1
        assert by_department[0].id == allocated_employee.id


def test_list_all_active_only_excludes_inactive() -> None:
    with _session() as session:
        active_user = _create_user(session, username="active", email="active@example.test")
        inactive_user = _create_user(session, username="inactive", email="inactive@example.test")
        repo = SqlAlchemyEmployeeRepository(session)
        repo.create(
            user_id=active_user,
            full_name="Active Employee",
            email="active@example.test",
            department="Backend",
            designation="Developer",
        )
        inactive = repo.create(
            user_id=inactive_user,
            full_name="Inactive Employee",
            email="inactive@example.test",
            department="Backend",
            designation="Developer",
        )
        repo.set_active(inactive.id, is_active=False)
        session.commit()

        active_only = repo.list_all()
        all_employees = repo.list_all(active_only=False)

        assert len(active_only) == 1
        assert active_only[0].email == "active@example.test"
        assert len(all_employees) == 2


def test_update_changes_provided_fields() -> None:
    with _session() as session:
        user_id = _create_user(session, username="ravi", email="ravi@example.test")
        employee_id = _create_employee(session, user_id=user_id, email="ravi@example.test")
        repo = SqlAlchemyEmployeeRepository(session)

        updated = repo.update(
            employee_id,
            department="DevOps",
            designation="Lead Developer",
        )
        session.commit()

        assert updated.department == "DevOps"
        assert updated.designation == "Lead Developer"
        assert updated.full_name == "Ravi Kumar"
        assert updated.email == "ravi@example.test"


def test_update_raises_when_employee_missing() -> None:
    with _session() as session:
        repo = SqlAlchemyEmployeeRepository(session)
        with pytest.raises(NotFoundError):
            repo.update(999, department="DevOps")


def test_set_active_changes_flag() -> None:
    with _session() as session:
        user_id = _create_user(session, username="ravi", email="ravi@example.test")
        employee_id = _create_employee(session, user_id=user_id, email="ravi@example.test")
        repo = SqlAlchemyEmployeeRepository(session)

        updated = repo.set_active(employee_id, is_active=False)
        session.commit()

        assert updated.is_active is False
        reloaded = repo.find_by_id(employee_id)
        assert reloaded is not None
        assert reloaded.is_active is False


def test_set_active_raises_when_employee_missing() -> None:
    with _session() as session:
        repo = SqlAlchemyEmployeeRepository(session)
        with pytest.raises(NotFoundError):
            repo.set_active(999, is_active=False)
