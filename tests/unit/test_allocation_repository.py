"""Unit tests for SQLAlchemy allocation repository."""

from datetime import date

import pytest
from sqlalchemy.orm import Session

from prm.domain.enums import AllocationStatus, Role
from prm.domain.exceptions import NotFoundError
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


def _seed_manager_and_user(session: Session) -> tuple[int, int]:
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
    session.flush()
    return manager_id, user_id


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


def _create_second_user(session: Session, *, manager_id: int) -> int:
    return create_user(
        session,
        username="employee2",
        email="employee2@example.test",
        full_name="Neha Joshi",
        role=Role.ENGINEER,
        manager_id=manager_id,
    )


def _create_allocation(
    session: Session,
    *,
    user_id: int,
    project_id: int,
    created_by_user_id: int,
    status: AllocationStatus = AllocationStatus.ACTIVE,
    from_date: date | None = None,
    to_date: date | None = None,
    utilisation_percent: int = 50,
) -> int:
    allocation = AllocationModel(
        user_id=user_id,
        project_id=project_id,
        utilisation_percent=utilisation_percent,
        from_date=from_date or date(2026, 6, 1),
        to_date=to_date,
        status=status,
        created_by_user_id=created_by_user_id,
    )
    session.add(allocation)
    session.flush()
    return allocation.id


def test_find_active_by_user_returns_only_active_allocations() -> None:
    with _session() as session:
        manager_id, user_id = _seed_manager_and_user(session)
        project_id = _create_project(session, manager_user_id=manager_id)
        active_id = _create_allocation(
            session,
            user_id=user_id,
            project_id=project_id,
            created_by_user_id=manager_id,
        )
        _create_allocation(
            session,
            user_id=user_id,
            project_id=project_id,
            created_by_user_id=manager_id,
            status=AllocationStatus.ENDED,
            to_date=date(2026, 5, 31),
        )
        session.commit()
        repo = SqlAlchemyAllocationRepository(session)

        active = repo.find_active_by_user(user_id)

        assert len(active) == 1
        assert active[0].id == active_id
        assert active[0].status == AllocationStatus.ACTIVE


def test_find_active_by_user_returns_empty_when_none() -> None:
    with _session() as session:
        _, user_id = _seed_manager_and_user(session)
        session.commit()
        repo = SqlAlchemyAllocationRepository(session)

        assert repo.find_active_by_user(user_id) == []


def test_end_active_for_user_sets_to_date_and_status() -> None:
    with _session() as session:
        manager_id, user_id = _seed_manager_and_user(session)
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
            user_id=user_id,
            project_id=project_a,
            created_by_user_id=manager_id,
        )
        second_id = _create_allocation(
            session,
            user_id=user_id,
            project_id=project_b.id,
            created_by_user_id=manager_id,
        )
        session.commit()
        repo = SqlAlchemyAllocationRepository(session)
        end_date = date(2026, 6, 7)

        ended = repo.end_active_for_user(user_id, as_of=end_date)
        session.commit()

        assert len(ended) == 2
        assert {allocation.id for allocation in ended} == {first_id, second_id}
        for allocation in ended:
            assert allocation.status == AllocationStatus.ENDED
            assert allocation.to_date == end_date

        assert repo.find_active_by_user(user_id) == []


def test_end_active_for_user_returns_empty_when_none_active() -> None:
    with _session() as session:
        _, user_id = _seed_manager_and_user(session)
        session.commit()
        repo = SqlAlchemyAllocationRepository(session)

        assert repo.end_active_for_user(user_id, as_of=date(2026, 6, 7)) == []


def test_list_active_returns_all_active_allocations() -> None:
    with _session() as session:
        manager_id, user_id = _seed_manager_and_user(session)
        second_user_id = _create_second_user(session, manager_id=manager_id)
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
            user_id=user_id,
            project_id=project_a,
            created_by_user_id=manager_id,
        )
        second_id = _create_allocation(
            session,
            user_id=user_id,
            project_id=project_b.id,
            created_by_user_id=manager_id,
        )
        third_id = _create_allocation(
            session,
            user_id=second_user_id,
            project_id=project_a,
            created_by_user_id=manager_id,
        )
        session.commit()
        repo = SqlAlchemyAllocationRepository(session)

        active = repo.list_active()

        assert len(active) == 3
        assert [allocation.id for allocation in active] == [first_id, second_id, third_id]


def test_list_active_filters_by_user_id() -> None:
    with _session() as session:
        manager_id, user_id = _seed_manager_and_user(session)
        second_user_id = _create_second_user(session, manager_id=manager_id)
        project_id = _create_project(session, manager_user_id=manager_id)
        first_id = _create_allocation(
            session,
            user_id=user_id,
            project_id=project_id,
            created_by_user_id=manager_id,
        )
        _create_allocation(
            session,
            user_id=second_user_id,
            project_id=project_id,
            created_by_user_id=manager_id,
        )
        session.commit()
        repo = SqlAlchemyAllocationRepository(session)

        active = repo.list_active(user_id=user_id)

        assert len(active) == 1
        assert active[0].id == first_id
        assert active[0].user_id == user_id


def test_list_active_filters_by_project_id() -> None:
    with _session() as session:
        manager_id, user_id = _seed_manager_and_user(session)
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
            user_id=user_id,
            project_id=project_a,
            created_by_user_id=manager_id,
        )
        _create_allocation(
            session,
            user_id=user_id,
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
        manager_id, user_id = _seed_manager_and_user(session)
        project_id = _create_project(session, manager_user_id=manager_id)
        active_id = _create_allocation(
            session,
            user_id=user_id,
            project_id=project_id,
            created_by_user_id=manager_id,
        )
        _create_allocation(
            session,
            user_id=user_id,
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
        _seed_manager_and_user(session)
        session.commit()
        repo = SqlAlchemyAllocationRepository(session)

        assert repo.list_active() == []


def test_find_by_id_returns_allocation() -> None:
    with _session() as session:
        manager_id, user_id = _seed_manager_and_user(session)
        project_id = _create_project(session, manager_user_id=manager_id)
        allocation_id = _create_allocation(
            session,
            user_id=user_id,
            project_id=project_id,
            created_by_user_id=manager_id,
        )
        session.commit()
        repo = SqlAlchemyAllocationRepository(session)

        allocation = repo.find_by_id(allocation_id)

        assert allocation is not None
        assert allocation.id == allocation_id
        assert allocation.user_id == user_id


def test_find_by_id_returns_none_when_missing() -> None:
    with _session() as session:
        repo = SqlAlchemyAllocationRepository(session)
        assert repo.find_by_id(999) is None


def test_find_overlapping_returns_active_allocations_in_range() -> None:
    with _session() as session:
        manager_id, user_id = _seed_manager_and_user(session)
        project_id = _create_project(session, manager_user_id=manager_id)
        overlapping_id = _create_allocation(
            session,
            user_id=user_id,
            project_id=project_id,
            created_by_user_id=manager_id,
            from_date=date(2026, 3, 1),
            to_date=date(2026, 6, 30),
        )
        _create_allocation(
            session,
            user_id=user_id,
            project_id=project_id,
            created_by_user_id=manager_id,
            from_date=date(2026, 8, 1),
            to_date=date(2026, 9, 30),
        )
        session.commit()
        repo = SqlAlchemyAllocationRepository(session)

        overlapping = repo.find_overlapping(
            user_id,
            date(2026, 5, 1),
            date(2026, 7, 31),
        )

        assert len(overlapping) == 1
        assert overlapping[0].id == overlapping_id


def test_find_overlapping_excludes_ended_allocations() -> None:
    with _session() as session:
        manager_id, user_id = _seed_manager_and_user(session)
        project_id = _create_project(session, manager_user_id=manager_id)
        _create_allocation(
            session,
            user_id=user_id,
            project_id=project_id,
            created_by_user_id=manager_id,
            from_date=date(2026, 3, 1),
            to_date=date(2026, 5, 31),
            status=AllocationStatus.ENDED,
        )
        session.commit()
        repo = SqlAlchemyAllocationRepository(session)

        assert repo.find_overlapping(user_id, date(2026, 4, 1), date(2026, 4, 30)) == []


def test_find_overlapping_respects_exclude_allocation_id() -> None:
    with _session() as session:
        manager_id, user_id = _seed_manager_and_user(session)
        project_id = _create_project(session, manager_user_id=manager_id)
        first_id = _create_allocation(
            session,
            user_id=user_id,
            project_id=project_id,
            created_by_user_id=manager_id,
            from_date=date(2026, 3, 1),
            to_date=date(2026, 6, 30),
        )
        session.commit()
        repo = SqlAlchemyAllocationRepository(session)

        overlapping = repo.find_overlapping(
            user_id,
            date(2026, 4, 1),
            date(2026, 5, 1),
            exclude_allocation_id=first_id,
        )

        assert overlapping == []


def test_create_persists_active_allocation() -> None:
    with _session() as session:
        manager_id, user_id = _seed_manager_and_user(session)
        project_id = _create_project(session, manager_user_id=manager_id)
        session.commit()
        repo = SqlAlchemyAllocationRepository(session)

        created = repo.create(
            user_id=user_id,
            project_id=project_id,
            utilisation_percent=50,
            from_date=date(2026, 6, 1),
            to_date=date(2026, 9, 30),
            created_by_user_id=manager_id,
        )
        session.commit()

        assert created.id is not None
        assert created.status == AllocationStatus.ACTIVE
        assert created.utilisation_percent == 50
        reloaded = repo.find_by_id(created.id)
        assert reloaded is not None
        assert reloaded.project_id == project_id


def test_end_by_id_sets_to_date_and_status() -> None:
    with _session() as session:
        manager_id, user_id = _seed_manager_and_user(session)
        project_id = _create_project(session, manager_user_id=manager_id)
        allocation_id = _create_allocation(
            session,
            user_id=user_id,
            project_id=project_id,
            created_by_user_id=manager_id,
        )
        session.commit()
        repo = SqlAlchemyAllocationRepository(session)
        end_date = date(2026, 6, 14)

        ended = repo.end_by_id(allocation_id, as_of=end_date)
        session.commit()

        assert ended.id == allocation_id
        assert ended.status == AllocationStatus.ENDED
        assert ended.to_date == end_date
        assert repo.find_active_by_user(user_id) == []


def test_end_by_id_raises_when_missing() -> None:
    with _session() as session:
        repo = SqlAlchemyAllocationRepository(session)
        with pytest.raises(NotFoundError, match="Allocation 999 not found"):
            repo.end_by_id(999, as_of=date(2026, 6, 14))


def test_end_by_id_raises_when_already_ended() -> None:
    with _session() as session:
        manager_id, user_id = _seed_manager_and_user(session)
        project_id = _create_project(session, manager_user_id=manager_id)
        allocation_id = _create_allocation(
            session,
            user_id=user_id,
            project_id=project_id,
            created_by_user_id=manager_id,
            status=AllocationStatus.ENDED,
            to_date=date(2026, 5, 31),
        )
        session.commit()
        repo = SqlAlchemyAllocationRepository(session)
        with pytest.raises(NotFoundError, match="not active"):
            repo.end_by_id(allocation_id, as_of=date(2026, 6, 14))


def test_list_active_for_manager_returns_only_owned_project_allocations() -> None:
    with _session() as session:
        manager_id, user_id = _seed_manager_and_user(session)
        seed_rbac(session)
        other_manager_id = create_user(
            session,
            full_name="Other Manager",
            username="other",
            email="other@example.test",
            role=Role.MANAGER,
        )
        owned_project_id = _create_project(session, manager_user_id=manager_id)
        other_project = ProjectModel(
            name="Other Project",
            description="Other",
            start_date=date(2026, 1, 1),
            manager_user_id=other_manager_id,
        )
        session.add(other_project)
        session.flush()
        owned_allocation_id = _create_allocation(
            session,
            user_id=user_id,
            project_id=owned_project_id,
            created_by_user_id=manager_id,
        )
        _create_allocation(
            session,
            user_id=user_id,
            project_id=other_project.id,
            created_by_user_id=other_manager_id,
        )
        session.commit()
        repo = SqlAlchemyAllocationRepository(session)

        allocations = repo.list_active_for_manager(manager_id)

        assert len(allocations) == 1
        assert allocations[0].id == owned_allocation_id
        assert allocations[0].project_id == owned_project_id
