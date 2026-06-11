"""Unit tests for ResourceDashboardService."""

from datetime import date

import pytest
from sqlalchemy.orm import Session

from prm.application.resource_dashboard_service import ResourceDashboardService
from prm.domain.enums import (
    AllocationStatus,
    ProficiencyLevel,
    ResourceWorkStatus,
    Role,
    SkillCategory,
)
from prm.domain.exceptions import NotFoundError, UnauthorizedError
from prm.infrastructure.db.models import AllocationModel, ProjectModel
from prm.infrastructure.db.repositories import (
    SqlAlchemyAllocationRepository,
    SqlAlchemyProjectRepository,
    SqlAlchemySkillRepository,
    SqlAlchemyUserRepository,
    SqlAlchemyUserSkillRepository,
)
from tests.unit.engineer_fixtures import (
    create_allocation_tables,
    create_memory_session,
    create_skill_tables,
    create_user,
    seed_rbac,
    set_engineer_status,
)


class _FakeTimesheetRepository:
    def __init__(self, tags: list[str] | None = None) -> None:
        self._tags = tags or []

    def list_recent_activity_tags(
        self,
        user_id: int,
        *,
        weeks: int = 4,
        as_of: date | None = None,
    ) -> list[str]:
        return list(self._tags)


def _session() -> Session:
    session = create_memory_session(include_project=True)
    create_allocation_tables(session)
    create_skill_tables(session)
    return session


def _service(session: Session, *, tags: list[str] | None = None) -> ResourceDashboardService:
    return ResourceDashboardService(
        user_repository=SqlAlchemyUserRepository(session),
        user_skill_repository=SqlAlchemyUserSkillRepository(session),
        skill_repository=SqlAlchemySkillRepository(session),
        allocation_repository=SqlAlchemyAllocationRepository(session),
        project_repository=SqlAlchemyProjectRepository(session),
        timesheet_repository=_FakeTimesheetRepository(tags),
    )


def _seed_bench_and_allocated(session: Session) -> tuple[int, int, int]:
    seed_rbac(session)
    manager_id = create_user(
        session,
        username="manager",
        email="manager@example.test",
        full_name="Manager User",
        role=Role.MANAGER,
    )
    bench_id = create_user(
        session,
        username="bench",
        email="bench@example.test",
        full_name="Priya Sharma",
        role=Role.ENGINEER,
        manager_id=manager_id,
    )
    allocated_id = create_user(
        session,
        username="allocated",
        email="allocated@example.test",
        full_name="Neha Joshi",
        role=Role.ENGINEER,
        manager_id=manager_id,
    )
    set_engineer_status(
        session,
        allocated_id,
        utilisation_percent=75,
        work_status=ResourceWorkStatus.ALLOCATED,
    )
    skill_repo = SqlAlchemySkillRepository(session)
    react = skill_repo.create(name="React", category=SkillCategory.FRONTEND)
    SqlAlchemyUserSkillRepository(session).assign(
        user_id=bench_id,
        skill_id=react.id,
        proficiency=ProficiencyLevel.INTERMEDIATE,
    )
    project = ProjectModel(
        name="Alpha Portal",
        description="Test project",
        start_date=date(2026, 1, 1),
        manager_user_id=manager_id,
    )
    session.add(project)
    session.flush()
    session.add(
        AllocationModel(
            user_id=allocated_id,
            project_id=project.id,
            utilisation_percent=75,
            from_date=date(2026, 3, 1),
            to_date=date(2026, 8, 31),
            status=AllocationStatus.ACTIVE,
            created_by_user_id=manager_id,
        )
    )
    session.flush()
    return manager_id, bench_id, allocated_id


def test_get_dashboard_splits_bench_and_active_with_counts() -> None:
    with _session() as session:
        manager_id, bench_id, allocated_id = _seed_bench_and_allocated(session)
        session.commit()
        service = _service(session)

        dashboard = service.get_dashboard(manager_id)

        assert dashboard.bench_count == 1
        assert dashboard.on_bench[0].user_id == bench_id
        assert dashboard.on_bench[0].skill_names == ("React",)
        assert len(dashboard.active) == 1
        assert dashboard.active[0].user_id == allocated_id
        assert dashboard.active[0].utilisation_percent == 75
        assert dashboard.active[0].availability_percent == 25
        assert dashboard.partial_count == 1


def test_get_dashboard_excludes_employees_not_on_manager_team() -> None:
    with _session() as session:
        manager_id, bench_id, allocated_id = _seed_bench_and_allocated(session)
        seed_rbac(session)
        other_manager_id = create_user(
            session,
            full_name="Other Manager",
            username="other.manager",
            email="other@example.test",
            role=Role.MANAGER,
        )
        outside_id = create_user(
            session,
            full_name="Outside Team",
            username="outside",
            email="outside@example.test",
            role=Role.ENGINEER,
            manager_id=other_manager_id,
        )
        session.commit()
        service = _service(session)

        dashboard = service.get_dashboard(manager_id)

        visible_ids = {row.user_id for row in dashboard.on_bench} | {
            row.user_id for row in dashboard.active
        }
        assert bench_id in visible_ids
        assert allocated_id in visible_ids
        assert outside_id not in visible_ids


def test_get_engineer_detail_returns_allocations_skills_and_tags() -> None:
    with _session() as session:
        manager_id, _, allocated_id = _seed_bench_and_allocated(session)
        session.commit()
        service = _service(session, tags=["Microservices", "Backend Api"])

        detail = service.get_engineer_detail(manager_id, allocated_id)

        assert detail.full_name == "Neha Joshi"
        assert detail.work_status == ResourceWorkStatus.ALLOCATED
        assert detail.current_utilisation_percent == 75
        assert len(detail.active_allocations) == 1
        assert detail.active_allocations[0].project_name == "Alpha Portal"
        assert detail.recent_activity_tags == ("Microservices", "Backend Api")


def test_get_engineer_detail_raises_when_missing() -> None:
    with _session() as session:
        manager_id, _, _ = _seed_bench_and_allocated(session)
        session.commit()
        service = _service(session)

        with pytest.raises(NotFoundError, match="Engineer 999 not found"):
            service.get_engineer_detail(manager_id, 999)


def test_get_engineer_detail_raises_when_not_on_manager_team() -> None:
    with _session() as session:
        manager_id, _, allocated_id = _seed_bench_and_allocated(session)
        seed_rbac(session)
        other_manager_id = create_user(
            session,
            full_name="Other Manager",
            username="other.manager",
            email="other@example.test",
            role=Role.MANAGER,
        )
        session.commit()
        service = _service(session)

        with pytest.raises(UnauthorizedError, match="not assigned to your team"):
            service.get_engineer_detail(other_manager_id, allocated_id)
