"""Unit tests for ManagerProjectService."""

from datetime import UTC, date, datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from prm.application.authorization_service import AuthorizationService
from prm.application.manager_project_service import ManagerProjectService
from prm.domain.entities.project_health_snapshot import ProjectHealthSnapshot
from prm.domain.enums import (
    MilestoneStatus,
    ProjectHealthStatus,
    ProjectStatus,
    Role,
)
from prm.domain.exceptions import NotFoundError, UnauthorizedError
from prm.infrastructure.db.models import (
    AllocationModel,
    EmployeeModel,
    MilestoneModel,
    ProjectModel,
    UserModel,
)
from prm.infrastructure.db.repositories import (
    SqlAlchemyAllocationRepository,
    SqlAlchemyEmployeeRepository,
    SqlAlchemyMilestoneRepository,
    SqlAlchemyProjectRepository,
    SqlAlchemyUserRepository,
)
from prm.infrastructure.security.password import BcryptPasswordHasher


class _FakeHealthSnapshotRepository:
    def __init__(self, snapshot: ProjectHealthSnapshot | None = None) -> None:
        self._snapshot = snapshot

    def find_latest_for_project(self, project_id: int) -> ProjectHealthSnapshot | None:
        _ = project_id
        return self._snapshot


def _session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    UserModel.__table__.create(engine, checkfirst=True)
    EmployeeModel.__table__.create(engine, checkfirst=True)
    ProjectModel.__table__.create(engine, checkfirst=True)
    MilestoneModel.__table__.create(engine, checkfirst=True)
    AllocationModel.__table__.create(engine, checkfirst=True)
    return Session(engine)


def _service(
    session: Session,
    *,
    snapshot: ProjectHealthSnapshot | None = None,
) -> ManagerProjectService:
    project_repo = SqlAlchemyProjectRepository(session)
    return ManagerProjectService(
        project_repository=project_repo,
        milestone_repository=SqlAlchemyMilestoneRepository(session),
        allocation_repository=SqlAlchemyAllocationRepository(session),
        employee_repository=SqlAlchemyEmployeeRepository(session),
        health_snapshot_repository=_FakeHealthSnapshotRepository(snapshot),
        authorization=AuthorizationService(project_repo),
    )


def _seed_manager_project(
    session: Session,
    *,
    health_status: ProjectHealthStatus = ProjectHealthStatus.AT_RISK,
) -> tuple[int, int]:
    user_repo = SqlAlchemyUserRepository(session)
    hasher = BcryptPasswordHasher()
    manager = user_repo.create(
        full_name="Ankit Shah",
        username="ankit",
        email="ankit@example.test",
        password_hash=hasher.hash("TempPass1"),
        role=Role.MANAGER,
    )
    project_repo = SqlAlchemyProjectRepository(session)
    project = project_repo.create(
        name="Alpha Portal",
        description="Customer portal rewrite",
        start_date=date(2026, 3, 1),
        end_date=date(2026, 6, 30),
        status=ProjectStatus.ACTIVE,
        manager_user_id=manager.id,
    )
    project_model = session.get(ProjectModel, project.id)
    assert project_model is not None
    project_model.health_status = health_status
    project_model.health_computed_at = datetime(2026, 5, 12, 10, 0, tzinfo=UTC)
    session.flush()
    return manager.id, project.id


def test_list_my_projects_returns_owned_projects_only() -> None:
    with _session() as session:
        manager_id, owned_project_id = _seed_manager_project(session)
        other_manager = SqlAlchemyUserRepository(session)
        hasher = BcryptPasswordHasher()
        other = other_manager.create(
            full_name="Other Manager",
            username="other",
            email="other@example.test",
            password_hash=hasher.hash("TempPass1"),
            role=Role.MANAGER,
        )
        SqlAlchemyProjectRepository(session).create(
            name="Beta CRM",
            description=None,
            start_date=date(2026, 4, 1),
            end_date=date(2026, 8, 15),
            status=ProjectStatus.ACTIVE,
            manager_user_id=other.id,
        )
        session.commit()
        service = _service(session)

        result = service.list_my_projects(manager_id)

        assert result.total == 1
        assert result.projects[0].project_id == owned_project_id
        assert result.projects[0].name == "Alpha Portal"
        assert result.projects[0].health_status == ProjectHealthStatus.AT_RISK


def test_get_project_detail_includes_milestones_allocations_and_risk_flags() -> None:
    with _session() as session:
        manager_id, project_id = _seed_manager_project(session)
        user_repo = SqlAlchemyUserRepository(session)
        hasher = BcryptPasswordHasher()
        employee_user = user_repo.create(
            full_name="Employee User",
            username="employee",
            email="employee@example.test",
            password_hash=hasher.hash("TempPass1"),
            role=Role.EMPLOYEE,
        )
        employee = SqlAlchemyEmployeeRepository(session).create(
            user_id=employee_user.id,
            full_name="Ravi Kumar",
            email="employee@example.test",
            department="Backend",
            designation="Developer",
        )
        milestone_repo = SqlAlchemyMilestoneRepository(session)
        milestone_repo.create(
            project_id=project_id,
            title="Backend API",
            due_date=date(2026, 4, 15),
            status=MilestoneStatus.IN_PROGRESS,
            sequence_order=2,
        )
        session.add(
            AllocationModel(
                employee_id=employee.id,
                project_id=project_id,
                utilisation_percent=50,
                from_date=date(2026, 3, 1),
                to_date=date(2026, 6, 30),
                created_by_user_id=manager_id,
            )
        )
        session.commit()
        snapshot = ProjectHealthSnapshot(
            id=1,
            project_id=project_id,
            status=ProjectHealthStatus.AT_RISK,
            risk_flags=("Backend API milestone is 5 days overdue",),
            computed_at=datetime(2026, 5, 12, 10, 0, tzinfo=UTC),
        )
        service = _service(session, snapshot=snapshot)

        detail = service.get_project_detail(
            manager_id,
            project_id,
            as_of=date(2026, 4, 20),
        )

        assert detail.name == "Alpha Portal"
        assert detail.health_status == ProjectHealthStatus.AT_RISK
        assert detail.risk_flags == ("Backend API milestone is 5 days overdue",)
        assert len(detail.milestones) == 1
        assert detail.milestones[0].is_overdue is True
        assert len(detail.allocated_resources) == 1
        assert detail.allocated_resources[0].employee_full_name == "Ravi Kumar"


def test_get_project_detail_raises_when_not_owner() -> None:
    with _session() as session:
        manager_id, project_id = _seed_manager_project(session)
        other_manager = SqlAlchemyUserRepository(session)
        hasher = BcryptPasswordHasher()
        other = other_manager.create(
            full_name="Other Manager",
            username="other",
            email="other@example.test",
            password_hash=hasher.hash("TempPass1"),
            role=Role.MANAGER,
        )
        session.commit()
        service = _service(session)

        with pytest.raises(UnauthorizedError):
            service.get_project_detail(other.id, project_id)


def test_get_project_detail_raises_when_project_missing() -> None:
    with _session() as session:
        manager_id, _ = _seed_manager_project(session)
        session.commit()
        service = _service(session)

        with pytest.raises(NotFoundError):
            service.get_project_detail(manager_id, 999)
