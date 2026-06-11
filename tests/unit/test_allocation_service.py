"""Unit tests for AllocationService."""

from datetime import date

import pytest
from sqlalchemy.orm import Session

from prm.application.allocation_service import AllocationService
from prm.application.authorization_service import AuthorizationService
from prm.application.utilisation_calculator import UtilisationCalculator
from prm.domain.enums import AllocationStatus, ProjectStatus, ResourceWorkStatus, Role
from prm.domain.exceptions import ConflictError, NotFoundError, UnauthorizedError, ValidationError
from prm.infrastructure.db.models import AllocationModel, ProjectModel
from prm.infrastructure.db.repositories import (
    SqlAlchemyAllocationRepository,
    SqlAlchemyProjectRepository,
    SqlAlchemyUserRepository,
)
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


def _service(session: Session) -> AllocationService:
    project_repo = SqlAlchemyProjectRepository(session)
    return AllocationService(
        allocation_repository=SqlAlchemyAllocationRepository(session),
        user_repository=SqlAlchemyUserRepository(session),
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
    seed_rbac(session)
    manager_id = create_user(
        session,
        username="manager",
        email="manager@example.test",
        full_name="Manager User",
        role=Role.MANAGER,
        department_name="Delivery",
        designation_name="Project Manager",
    )
    owner_id = manager_user_id or manager_id
    engineer_id = create_user(
        session,
        username="employee",
        email="employee@example.test",
        full_name="Ravi Kumar",
        role=Role.ENGINEER,
        manager_id=owner_id,
    )
    project = ProjectModel(
        name="Alpha Portal",
        description="Test project",
        start_date=date(2026, 1, 1),
        status=project_status,
        manager_user_id=owner_id,
    )
    session.add(project)
    session.flush()
    return owner_id, engineer_id, project.id


def test_allocate_direct_creates_allocation_and_updates_employee() -> None:
    with _session() as session:
        manager_id, user_id, project_id = _seed(session)
        session.commit()
        service = _service(session)

        allocation = service.allocate_direct(
            manager_id,
            project_id=project_id,
            user_id=user_id,
            utilisation_percent=50,
            from_date=date(2026, 6, 1),
            to_date=date(2026, 9, 30),
        )
        session.commit()

        assert allocation.status == AllocationStatus.ACTIVE
        assert allocation.utilisation_percent == 50
        engineer = SqlAlchemyUserRepository(session).find_by_id(user_id)
        assert engineer is not None
        assert engineer.utilisation_percent == 50
        assert engineer.work_status == ResourceWorkStatus.ALLOCATED


def test_allocate_direct_raises_conflict_when_over_cap() -> None:
    with _session() as session:
        manager_id, user_id, project_id = _seed(session)
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
        service = _service(session)

        with pytest.raises(ConflictError, match="125%"):
            service.allocate_direct(
                manager_id,
                project_id=project_id,
                user_id=user_id,
                utilisation_percent=50,
                from_date=date(2026, 6, 1),
                to_date=date(2026, 9, 30),
            )


@pytest.mark.parametrize(
    "project_status",
    [ProjectStatus.ON_HOLD, ProjectStatus.COMPLETED],
)
def test_allocate_direct_raises_when_project_not_allocatable(
    project_status: ProjectStatus,
) -> None:
    with _session() as session:
        manager_id, user_id, project_id = _seed(
            session,
            project_status=project_status,
        )
        session.commit()
        service = _service(session)

        with pytest.raises(ValidationError, match="ACTIVE or PLANNED"):
            service.allocate_direct(
                manager_id,
                project_id=project_id,
                user_id=user_id,
                utilisation_percent=50,
                from_date=date(2026, 6, 1),
                to_date=date(2026, 9, 30),
            )


def test_allocate_direct_raises_when_not_project_owner() -> None:
    with _session() as session:
        manager_id, user_id, project_id = _seed(session)
        outsider = create_user(
            session,
            username="outsider",
            email="outsider@example.test",
            full_name="Outsider",
            role=Role.MANAGER,
            department_name="Delivery",
            designation_name="Project Manager",
        )
        session.commit()
        service = _service(session)

        with pytest.raises(UnauthorizedError, match="project owner"):
            service.allocate_direct(
                outsider,
                project_id=project_id,
                user_id=user_id,
                utilisation_percent=50,
                from_date=date(2026, 6, 1),
                to_date=date(2026, 9, 30),
            )


def test_end_allocation_sets_ended_and_returns_employee_to_bench() -> None:
    with _session() as session:
        manager_id, user_id, project_id = _seed(session)
        allocation = AllocationModel(
            user_id=user_id,
            project_id=project_id,
            utilisation_percent=50,
            from_date=date(2026, 3, 1),
            to_date=date(2026, 8, 31),
            status=AllocationStatus.ACTIVE,
            created_by_user_id=manager_id,
        )
        session.add(allocation)
        session.flush()
        set_engineer_status(
            session,
            user_id,
            utilisation_percent=50,
            work_status=ResourceWorkStatus.ALLOCATED,
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
        engineer = SqlAlchemyUserRepository(session).find_by_id(user_id)
        assert engineer is not None
        assert engineer.work_status == ResourceWorkStatus.BENCH
        assert engineer.utilisation_percent == 0


def test_list_project_allocations_returns_active_rows_for_owner() -> None:
    with _session() as session:
        manager_id, user_id, project_id = _seed(session)
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
        service = _service(session)

        allocations = service.list_project_allocations(manager_id, project_id)

        assert len(allocations) == 1
        assert allocations[0].user_full_name == "Ravi Kumar"
        assert allocations[0].project_name == "Alpha Portal"


def test_end_allocation_raises_when_allocation_missing() -> None:
    with _session() as session:
        manager_id, _, _ = _seed(session)
        session.commit()
        service = _service(session)

        with pytest.raises(NotFoundError, match="Allocation 999 not found"):
            service.end_allocation(manager_id, 999)


def test_allocate_direct_rejects_employee_not_on_manager_team() -> None:
    with _session() as session:
        _manager_id, user_id, _project_id = _seed(session)
        other_manager = create_user(
            session,
            username="other.manager",
            email="other@example.test",
            full_name="Other Manager",
            role=Role.MANAGER,
            department_name="Delivery",
            designation_name="Project Manager",
        )
        other_project = ProjectModel(
            name="Beta CRM",
            description="Other manager project",
            start_date=date(2026, 3, 1),
            status=ProjectStatus.ACTIVE,
            manager_user_id=other_manager,
        )
        session.add(other_project)
        session.commit()
        service = _service(session)

        with pytest.raises(UnauthorizedError, match="assigned to your team"):
            service.allocate_direct(
                other_manager,
                project_id=other_project.id,
                user_id=user_id,
                utilisation_percent=50,
                from_date=date(2026, 3, 1),
                to_date=date(2026, 6, 30),
            )
