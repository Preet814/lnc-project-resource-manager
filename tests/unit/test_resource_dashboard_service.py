"""Unit tests for ResourceDashboardService."""

from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from prm.application.resource_dashboard_service import ResourceDashboardService
from prm.domain.enums import (
    AllocationStatus,
    EmployeeWorkStatus,
    ProficiencyLevel,
    Role,
    SkillCategory,
)
from prm.domain.exceptions import NotFoundError, UnauthorizedError
from prm.infrastructure.db.models import (
    AllocationModel,
    EmployeeModel,
    EmployeeSkillModel,
    ProjectModel,
    SkillModel,
    UserModel,
)
from prm.infrastructure.db.repositories import (
    SqlAlchemyAllocationRepository,
    SqlAlchemyEmployeeRepository,
    SqlAlchemyEmployeeSkillRepository,
    SqlAlchemyProjectRepository,
    SqlAlchemySkillRepository,
    SqlAlchemyUserRepository,
)
from prm.infrastructure.security.password import BcryptPasswordHasher


class _FakeTimesheetRepository:
    def __init__(self, tags: list[str] | None = None) -> None:
        self._tags = tags or []

    def list_recent_activity_tags(
        self,
        employee_id: int,
        *,
        weeks: int = 4,
        as_of: date | None = None,
    ) -> list[str]:
        return list(self._tags)


def _session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    UserModel.__table__.create(engine, checkfirst=True)
    EmployeeModel.__table__.create(engine, checkfirst=True)
    ProjectModel.__table__.create(engine, checkfirst=True)
    AllocationModel.__table__.create(engine, checkfirst=True)
    SkillModel.__table__.create(engine, checkfirst=True)
    EmployeeSkillModel.__table__.create(engine, checkfirst=True)
    return Session(engine)


def _service(session: Session, *, tags: list[str] | None = None) -> ResourceDashboardService:
    return ResourceDashboardService(
        employee_repository=SqlAlchemyEmployeeRepository(session),
        employee_skill_repository=SqlAlchemyEmployeeSkillRepository(session),
        skill_repository=SqlAlchemySkillRepository(session),
        allocation_repository=SqlAlchemyAllocationRepository(session),
        project_repository=SqlAlchemyProjectRepository(session),
        timesheet_repository=_FakeTimesheetRepository(tags),
    )


def _seed_bench_and_allocated(session: Session) -> tuple[int, int, int]:
    user_repo = SqlAlchemyUserRepository(session)
    hasher = BcryptPasswordHasher()
    manager = user_repo.create(
        full_name="Manager User",
        username="manager",
        email="manager@example.test",
        password_hash=hasher.hash("TempPass1"),
        role=Role.MANAGER,
    )
    bench_user = user_repo.create(
        full_name="Bench User",
        username="bench",
        email="bench@example.test",
        password_hash=hasher.hash("TempPass1"),
        role=Role.EMPLOYEE,
    )
    allocated_user = user_repo.create(
        full_name="Allocated User",
        username="allocated",
        email="allocated@example.test",
        password_hash=hasher.hash("TempPass1"),
        role=Role.EMPLOYEE,
    )
    employee_repo = SqlAlchemyEmployeeRepository(session)
    bench_employee = employee_repo.create(
        user_id=bench_user.id,
        full_name="Priya Sharma",
        email="bench@example.test",
        department="Frontend",
        designation="Developer",
    )
    allocated_employee = employee_repo.create(
        user_id=allocated_user.id,
        full_name="Neha Joshi",
        email="allocated@example.test",
        department="Backend",
        designation="Developer",
    )
    employee_repo.update_utilisation_and_status(
        allocated_employee.id,
        current_utilisation_percent=75,
        work_status=EmployeeWorkStatus.ALLOCATED,
    )
    employee_repo.set_manager_id(bench_employee.id, manager_id=manager.id)
    employee_repo.set_manager_id(allocated_employee.id, manager_id=manager.id)
    skill_repo = SqlAlchemySkillRepository(session)
    react = skill_repo.create(name="React", category=SkillCategory.FRONTEND)
    SqlAlchemyEmployeeSkillRepository(session).assign(
        employee_id=bench_employee.id,
        skill_id=react.id,
        proficiency=ProficiencyLevel.INTERMEDIATE,
    )
    project = ProjectModel(
        name="Alpha Portal",
        description="Test project",
        start_date=date(2026, 1, 1),
        manager_user_id=manager.id,
    )
    session.add(project)
    session.flush()
    session.add(
        AllocationModel(
            employee_id=allocated_employee.id,
            project_id=project.id,
            utilisation_percent=75,
            from_date=date(2026, 3, 1),
            to_date=date(2026, 8, 31),
            status=AllocationStatus.ACTIVE,
            created_by_user_id=manager.id,
        )
    )
    session.flush()
    return manager.id, bench_employee.id, allocated_employee.id


def test_get_dashboard_splits_bench_and_active_with_counts() -> None:
    with _session() as session:
        manager_id, bench_id, allocated_id = _seed_bench_and_allocated(session)
        session.commit()
        service = _service(session)

        dashboard = service.get_dashboard(manager_id)

        assert dashboard.bench_count == 1
        assert dashboard.on_bench[0].employee_id == bench_id
        assert dashboard.on_bench[0].skill_names == ("React",)
        assert len(dashboard.active) == 1
        assert dashboard.active[0].employee_id == allocated_id
        assert dashboard.active[0].utilisation_percent == 75
        assert dashboard.active[0].availability_percent == 25
        assert dashboard.partial_count == 1


def test_get_dashboard_excludes_employees_not_on_manager_team() -> None:
    with _session() as session:
        manager_id, bench_id, allocated_id = _seed_bench_and_allocated(session)
        user_repo = SqlAlchemyUserRepository(session)
        hasher = BcryptPasswordHasher()
        other_manager = user_repo.create(
            full_name="Other Manager",
            username="other.manager",
            email="other@example.test",
            password_hash=hasher.hash("TempPass1"),
            role=Role.MANAGER,
        )
        other_user = user_repo.create(
            full_name="Outside Team",
            username="outside",
            email="outside@example.test",
            password_hash=hasher.hash("TempPass1"),
            role=Role.EMPLOYEE,
        )
        employee_repo = SqlAlchemyEmployeeRepository(session)
        outside_employee = employee_repo.create(
            user_id=other_user.id,
            full_name="Outside Team",
            email="outside@example.test",
            department="QA",
            designation="Tester",
        )
        employee_repo.set_manager_id(outside_employee.id, manager_id=other_manager.id)
        session.commit()
        service = _service(session)

        dashboard = service.get_dashboard(manager_id)

        visible_ids = {row.employee_id for row in dashboard.on_bench} | {
            row.employee_id for row in dashboard.active
        }
        assert bench_id in visible_ids
        assert allocated_id in visible_ids
        assert outside_employee.id not in visible_ids


def test_get_employee_detail_returns_allocations_skills_and_tags() -> None:
    with _session() as session:
        manager_id, _, allocated_id = _seed_bench_and_allocated(session)
        session.commit()
        service = _service(session, tags=["Microservices", "Backend Api"])

        detail = service.get_employee_detail(manager_id, allocated_id)

        assert detail.full_name == "Neha Joshi"
        assert detail.work_status == EmployeeWorkStatus.ALLOCATED
        assert detail.current_utilisation_percent == 75
        assert len(detail.active_allocations) == 1
        assert detail.active_allocations[0].project_name == "Alpha Portal"
        assert detail.recent_activity_tags == ("Microservices", "Backend Api")


def test_get_employee_detail_raises_when_missing() -> None:
    with _session() as session:
        manager_id, _, _ = _seed_bench_and_allocated(session)
        session.commit()
        service = _service(session)

        with pytest.raises(NotFoundError, match="Employee 999 not found"):
            service.get_employee_detail(manager_id, 999)


def test_get_employee_detail_raises_when_not_on_manager_team() -> None:
    with _session() as session:
        manager_id, _, allocated_id = _seed_bench_and_allocated(session)
        user_repo = SqlAlchemyUserRepository(session)
        hasher = BcryptPasswordHasher()
        other_manager = user_repo.create(
            full_name="Other Manager",
            username="other.manager",
            email="other@example.test",
            password_hash=hasher.hash("TempPass1"),
            role=Role.MANAGER,
        )
        session.commit()
        service = _service(session)

        with pytest.raises(UnauthorizedError, match="not assigned to your team"):
            service.get_employee_detail(other_manager.id, allocated_id)
