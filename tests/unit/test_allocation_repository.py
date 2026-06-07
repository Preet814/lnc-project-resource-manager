"""Unit tests for SQLAlchemy allocation repository."""

from datetime import date

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

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


def _seed_manager_and_employee(session: Session) -> tuple[int, int]:
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
    session.flush()
    return manager.id, employee.id


def _create_project(session: Session, *, manager_user_id: int) -> int:
    project = ProjectModel(
        name="Alpha Portal",
        description="Test project",
        start_date=date(2026, 1, 1),
        manager_user_id=manager_user_id,
    )
    session.add(project)
    session.flush()
    return project.id


def _create_second_employee(session: Session) -> int:
    user_repo = SqlAlchemyUserRepository(session)
    hasher = BcryptPasswordHasher()
    employee_user = user_repo.create(
        full_name="Second Employee",
        username="employee2",
        email="employee2@example.test",
        password_hash=hasher.hash("TempPass1"),
        role=Role.EMPLOYEE,
    )
    employee_repo = SqlAlchemyEmployeeRepository(session)
    employee = employee_repo.create(
        user_id=employee_user.id,
        full_name="Neha Joshi",
        email="employee2@example.test",
        department="Frontend",
        designation="Developer",
    )
    session.flush()
    return employee.id


def _create_allocation(
    session: Session,
    *,
    employee_id: int,
    project_id: int,
    created_by_user_id: int,
    status: AllocationStatus = AllocationStatus.ACTIVE,
    to_date: date | None = None,
) -> int:
    allocation = AllocationModel(
        employee_id=employee_id,
        project_id=project_id,
        utilisation_percent=50,
        from_date=date(2026, 6, 1),
        to_date=to_date,
        status=status,
        created_by_user_id=created_by_user_id,
    )
    session.add(allocation)
    session.flush()
    return allocation.id


def test_find_active_by_employee_returns_only_active_allocations() -> None:
    with _session() as session:
        manager_id, employee_id = _seed_manager_and_employee(session)
        project_id = _create_project(session, manager_user_id=manager_id)
        active_id = _create_allocation(
            session,
            employee_id=employee_id,
            project_id=project_id,
            created_by_user_id=manager_id,
        )
        _create_allocation(
            session,
            employee_id=employee_id,
            project_id=project_id,
            created_by_user_id=manager_id,
            status=AllocationStatus.ENDED,
            to_date=date(2026, 5, 31),
        )
        session.commit()
        repo = SqlAlchemyAllocationRepository(session)

        active = repo.find_active_by_employee(employee_id)

        assert len(active) == 1
        assert active[0].id == active_id
        assert active[0].status == AllocationStatus.ACTIVE


def test_find_active_by_employee_returns_empty_when_none() -> None:
    with _session() as session:
        _, employee_id = _seed_manager_and_employee(session)
        session.commit()
        repo = SqlAlchemyAllocationRepository(session)

        assert repo.find_active_by_employee(employee_id) == []


def test_end_active_for_employee_sets_to_date_and_status() -> None:
    with _session() as session:
        manager_id, employee_id = _seed_manager_and_employee(session)
        project_a = _create_project(session, manager_user_id=manager_id)
        project_b = ProjectModel(
            name="Beta CRM",
            description="Second project",
            start_date=date(2026, 1, 1),
            manager_user_id=manager_id,
        )
        session.add(project_b)
        session.flush()
        first_id = _create_allocation(
            session,
            employee_id=employee_id,
            project_id=project_a,
            created_by_user_id=manager_id,
        )
        second_id = _create_allocation(
            session,
            employee_id=employee_id,
            project_id=project_b.id,
            created_by_user_id=manager_id,
        )
        session.commit()
        repo = SqlAlchemyAllocationRepository(session)
        end_date = date(2026, 6, 7)

        ended = repo.end_active_for_employee(employee_id, as_of=end_date)
        session.commit()

        assert len(ended) == 2
        assert {allocation.id for allocation in ended} == {first_id, second_id}
        for allocation in ended:
            assert allocation.status == AllocationStatus.ENDED
            assert allocation.to_date == end_date

        assert repo.find_active_by_employee(employee_id) == []


def test_end_active_for_employee_returns_empty_when_none_active() -> None:
    with _session() as session:
        _, employee_id = _seed_manager_and_employee(session)
        session.commit()
        repo = SqlAlchemyAllocationRepository(session)

        assert repo.end_active_for_employee(employee_id, as_of=date(2026, 6, 7)) == []


def test_list_active_returns_all_active_allocations() -> None:
    with _session() as session:
        manager_id, employee_id = _seed_manager_and_employee(session)
        second_employee_id = _create_second_employee(session)
        project_a = _create_project(session, manager_user_id=manager_id)
        project_b = ProjectModel(
            name="Beta CRM",
            description="Second project",
            start_date=date(2026, 1, 1),
            manager_user_id=manager_id,
        )
        session.add(project_b)
        session.flush()
        first_id = _create_allocation(
            session,
            employee_id=employee_id,
            project_id=project_a,
            created_by_user_id=manager_id,
        )
        second_id = _create_allocation(
            session,
            employee_id=employee_id,
            project_id=project_b.id,
            created_by_user_id=manager_id,
        )
        third_id = _create_allocation(
            session,
            employee_id=second_employee_id,
            project_id=project_a,
            created_by_user_id=manager_id,
        )
        session.commit()
        repo = SqlAlchemyAllocationRepository(session)

        active = repo.list_active()

        assert len(active) == 3
        assert [allocation.id for allocation in active] == [first_id, second_id, third_id]


def test_list_active_filters_by_employee_id() -> None:
    with _session() as session:
        manager_id, employee_id = _seed_manager_and_employee(session)
        second_employee_id = _create_second_employee(session)
        project_id = _create_project(session, manager_user_id=manager_id)
        first_id = _create_allocation(
            session,
            employee_id=employee_id,
            project_id=project_id,
            created_by_user_id=manager_id,
        )
        _create_allocation(
            session,
            employee_id=second_employee_id,
            project_id=project_id,
            created_by_user_id=manager_id,
        )
        session.commit()
        repo = SqlAlchemyAllocationRepository(session)

        active = repo.list_active(employee_id=employee_id)

        assert len(active) == 1
        assert active[0].id == first_id
        assert active[0].employee_id == employee_id


def test_list_active_filters_by_project_id() -> None:
    with _session() as session:
        manager_id, employee_id = _seed_manager_and_employee(session)
        project_a = _create_project(session, manager_user_id=manager_id)
        project_b = ProjectModel(
            name="Beta CRM",
            description="Second project",
            start_date=date(2026, 1, 1),
            manager_user_id=manager_id,
        )
        session.add(project_b)
        session.flush()
        first_id = _create_allocation(
            session,
            employee_id=employee_id,
            project_id=project_a,
            created_by_user_id=manager_id,
        )
        _create_allocation(
            session,
            employee_id=employee_id,
            project_id=project_b.id,
            created_by_user_id=manager_id,
        )
        session.commit()
        repo = SqlAlchemyAllocationRepository(session)

        active = repo.list_active(project_id=project_a)

        assert len(active) == 1
        assert active[0].id == first_id
        assert active[0].project_id == project_a


def test_list_active_excludes_ended_allocations() -> None:
    with _session() as session:
        manager_id, employee_id = _seed_manager_and_employee(session)
        project_id = _create_project(session, manager_user_id=manager_id)
        active_id = _create_allocation(
            session,
            employee_id=employee_id,
            project_id=project_id,
            created_by_user_id=manager_id,
        )
        _create_allocation(
            session,
            employee_id=employee_id,
            project_id=project_id,
            created_by_user_id=manager_id,
            status=AllocationStatus.ENDED,
            to_date=date(2026, 5, 31),
        )
        session.commit()
        repo = SqlAlchemyAllocationRepository(session)

        active = repo.list_active()

        assert len(active) == 1
        assert active[0].id == active_id


def test_list_active_returns_empty_when_none() -> None:
    with _session() as session:
        _seed_manager_and_employee(session)
        session.commit()
        repo = SqlAlchemyAllocationRepository(session)

        assert repo.list_active() == []
