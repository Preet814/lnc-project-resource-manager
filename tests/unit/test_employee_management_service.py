"""Unit tests for UserProfileService."""

from datetime import date

import pytest
from sqlalchemy.orm import Session

from prm.application.user_management_service import UserManagementService
from prm.application.user_profile_service import UserProfileService
from prm.domain.enums import (
    AllocationStatus,
    ProjectStatus,
    ResourceWorkStatus,
    Role,
    UserAccountStatus,
)
from prm.domain.exceptions import NotFoundError, ValidationError
from prm.infrastructure.db.models import AllocationModel, ProjectModel
from prm.infrastructure.db.repositories import (
    SqlAlchemyAllocationRepository,
    SqlAlchemyUserRepository,
)
from prm.infrastructure.db.seed import seed_bootstrap_admin
from prm.infrastructure.security.password import BcryptPasswordHasher
from tests.unit.credentials import TEST_EMAIL, TEST_FULL_NAME, TEST_PASSWORD, TEST_USERNAME
from tests.unit.engineer_fixtures import (
    create_allocation_tables,
    create_memory_session,
    create_user,
    seed_rbac,
    set_engineer_status,
)


def _session() -> Session:
    session = create_memory_session(include_project=True)
    create_allocation_tables(session)
    return session


def _service(session: Session) -> UserProfileService:
    return UserProfileService(
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


def test_create_employee_updates_engineer_profile() -> None:
    with _session() as session:
        seed_rbac(session)
        user_id = create_user(
            session,
            username="ravi",
            email="ravi@example.test",
            full_name="Ravi Kumar",
            role=Role.ENGINEER,
        )
        created = _service(session).create_employee(
            user_id=user_id,
            full_name="Ravi Kumar",
            email="ravi@example.test",
            department="Backend",
            designation="SE",
        )
        session.commit()

        assert created.id == user_id
        assert created.work_status == ResourceWorkStatus.BENCH
        assert created.is_active()


def test_create_employee_fails_when_user_missing() -> None:
    with _session() as session:
        seed_rbac(session)
        with pytest.raises(NotFoundError):
            _service(session).create_employee(
                user_id=999,
                full_name="Missing User",
                email="missing@example.test",
                department="Backend",
                designation="SE",
            )


def test_create_employee_fails_for_admin_user() -> None:
    with _session() as session:
        _seed_admin(session)
        with pytest.raises(ValidationError, match="Engineer or Manager"):
            _service(session).create_employee(
                user_id=1,
                full_name="Admin Profile",
                email="admin-profile@example.test",
                department="IT",
                designation="System Administrator",
            )


def test_list_employees_returns_summaries_and_counts() -> None:
    with _session() as session:
        seed_rbac(session)
        bench_id = create_user(
            session,
            username="bench",
            email="bench@example.test",
            full_name="Bench Engineer",
            role=Role.ENGINEER,
        )
        allocated_id = create_user(
            session,
            username="allocated",
            email="allocated@example.test",
            full_name="Allocated Engineer",
            role=Role.ENGINEER,
        )
        set_engineer_status(
            session,
            allocated_id,
            utilisation_percent=50,
            work_status=ResourceWorkStatus.ALLOCATED,
        )
        session.commit()

        result = _service(session).list_employees()

        assert result.total == 2
        assert result.bench_count == 1
        assert result.allocated_count == 1
        ids = {summary.id for summary in result.engineers}
        assert bench_id in ids
        assert allocated_id in ids


def test_deactivate_employee_ends_allocations_and_deactivates_user() -> None:
    with _session() as session:
        seed_rbac(session)
        manager_id = create_user(
            session,
            username="manager",
            email="manager@example.test",
            full_name="Manager",
            role=Role.MANAGER,
            department_name="Delivery",
            designation_name="Project Manager",
        )
        engineer_id = create_user(
            session,
            username="engineer",
            email="engineer@example.test",
            full_name="Engineer",
            role=Role.ENGINEER,
            manager_id=manager_id,
        )
        project = ProjectModel(
            name="Alpha",
            description="Test",
            start_date=date(2026, 1, 1),
            status=ProjectStatus.ACTIVE,
            manager_user_id=manager_id,
        )
        session.add(project)
        session.flush()
        session.add(
            AllocationModel(
                user_id=engineer_id,
                project_id=project.id,
                utilisation_percent=50,
                from_date=date(2026, 3, 1),
                to_date=None,
                status=AllocationStatus.ACTIVE,
                created_by_user_id=manager_id,
            )
        )
        session.commit()

        deactivated = _service(session).deactivate_employee(engineer_id)
        session.commit()

        assert deactivated.account_status == UserAccountStatus.INACTIVE
        allocations = SqlAlchemyAllocationRepository(session).find_active_by_user(engineer_id)
        assert allocations == []
