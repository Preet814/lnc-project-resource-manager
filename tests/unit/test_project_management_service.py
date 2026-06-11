"""Unit tests for ProjectManagementService."""

from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from prm.application.project_management_service import ProjectManagementService
from prm.application.user_management_service import UserManagementService
from prm.domain.enums import MilestoneStatus, ProjectStatus, Role
from prm.domain.exceptions import NotFoundError, ValidationError
from prm.infrastructure.db.models import MilestoneModel, ProjectModel, UserModel
from prm.infrastructure.db.repositories import (
    SqlAlchemyMilestoneRepository,
    SqlAlchemyProjectRepository,
    SqlAlchemyUserRepository,
)
from prm.infrastructure.db.seed import seed_bootstrap_admin
from prm.infrastructure.security.password import BcryptPasswordHasher
from tests.unit.engineer_fixtures import create_memory_session, seed_rbac
from tests.unit.credentials import TEST_EMAIL, TEST_FULL_NAME, TEST_PASSWORD, TEST_USERNAME


def _session() -> Session:
    return create_memory_session(include_project=True)


def _service(session: Session) -> ProjectManagementService:
    return ProjectManagementService(
        project_repository=SqlAlchemyProjectRepository(session),
        user_repository=SqlAlchemyUserRepository(session),
        milestone_repository=SqlAlchemyMilestoneRepository(session),
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
    full_name: str | None = None,
) -> int:
    seed_rbac(session)
    created = _user_service(session).create_user(
        full_name=full_name or f"{username} Name",
        email=email,
        username=username,
        temporary_password="TempPass1",
        role=role,
    )
    session.flush()
    return created.id


def test_create_project_persists_with_manager() -> None:
    with _session() as session:
        manager_id = _create_user(
            session,
            username="ankit",
            email="ankit@example.test",
            role=Role.MANAGER,
            full_name="Ankit Shah",
        )
        created = _service(session).create_project(
            name="Alpha Portal",
            description="Customer portal rewrite",
            start_date=date(2026, 3, 1),
            end_date=date(2026, 6, 30),
            status=ProjectStatus.ACTIVE,
            manager_user_id=manager_id,
        )
        session.commit()

        assert created.name == "Alpha Portal"
        assert created.manager_user_id == manager_id
        assert created.status == ProjectStatus.ACTIVE


def test_create_project_fails_when_name_blank() -> None:
    with _session() as session:
        manager_id = _create_user(
            session,
            username="ankit",
            email="ankit@example.test",
            role=Role.MANAGER,
        )
        with pytest.raises(ValidationError, match="Project name is required"):
            _service(session).create_project(
                name="   ",
                description=None,
                start_date=date(2026, 3, 1),
                end_date=date(2026, 6, 30),
                status=ProjectStatus.ACTIVE,
                manager_user_id=manager_id,
            )


def test_create_project_fails_when_manager_missing() -> None:
    with _session() as session:
        with pytest.raises(NotFoundError):
            _service(session).create_project(
                name="Alpha Portal",
                description=None,
                start_date=date(2026, 3, 1),
                end_date=date(2026, 6, 30),
                status=ProjectStatus.ACTIVE,
                manager_user_id=999,
            )


def test_create_project_fails_when_manager_not_manager_role() -> None:
    with _session() as session:
        user_id = _create_user(
            session,
            username="ravi",
            email="ravi@example.test",
            role=Role.ENGINEER,
        )
        with pytest.raises(ValidationError, match="Manager account"):
            _service(session).create_project(
                name="Alpha Portal",
                description=None,
                start_date=date(2026, 3, 1),
                end_date=date(2026, 6, 30),
                status=ProjectStatus.ACTIVE,
                manager_user_id=user_id,
            )


def test_create_project_fails_when_manager_inactive() -> None:
    with _session() as session:
        _seed_admin(session)
        manager_id = _create_user(
            session,
            username="ankit",
            email="ankit@example.test",
            role=Role.MANAGER,
        )
        _user_service(session).deactivate_user(manager_id, actor_user_id=1)
        session.commit()

        with pytest.raises(ValidationError, match="Manager account"):
            _service(session).create_project(
                name="Alpha Portal",
                description=None,
                start_date=date(2026, 3, 1),
                end_date=date(2026, 6, 30),
                status=ProjectStatus.ACTIVE,
                manager_user_id=manager_id,
            )


def test_create_project_fails_when_start_after_end() -> None:
    with _session() as session:
        manager_id = _create_user(
            session,
            username="ankit",
            email="ankit@example.test",
            role=Role.MANAGER,
        )
        with pytest.raises(ValidationError, match="start date"):
            _service(session).create_project(
                name="Alpha Portal",
                description=None,
                start_date=date(2026, 7, 1),
                end_date=date(2026, 6, 30),
                status=ProjectStatus.ACTIVE,
                manager_user_id=manager_id,
            )


def test_list_projects_returns_summaries_and_counts() -> None:
    with _session() as session:
        manager_id = _create_user(
            session,
            username="ankit",
            email="ankit@example.test",
            role=Role.MANAGER,
            full_name="Ankit Shah",
        )
        service = _service(session)
        service.create_project(
            name="Alpha Portal",
            description=None,
            start_date=date(2026, 3, 1),
            end_date=date(2026, 6, 30),
            status=ProjectStatus.ACTIVE,
            manager_user_id=manager_id,
        )
        service.create_project(
            name="Delta Migrate",
            description=None,
            start_date=date(2026, 5, 1),
            end_date=date(2026, 9, 30),
            status=ProjectStatus.PLANNED,
            manager_user_id=manager_id,
        )
        session.commit()

        result = service.list_projects()

        assert result.total == 2
        assert result.active_count == 1
        assert result.planned_count == 1
        assert result.on_hold_count == 0
        assert result.projects[0].manager_full_name == "Ankit Shah"


def test_get_project_returns_project() -> None:
    with _session() as session:
        manager_id = _create_user(
            session,
            username="ankit",
            email="ankit@example.test",
            role=Role.MANAGER,
        )
        created = _service(session).create_project(
            name="Alpha Portal",
            description=None,
            start_date=date(2026, 3, 1),
            end_date=date(2026, 6, 30),
            status=ProjectStatus.ACTIVE,
            manager_user_id=manager_id,
        )
        session.commit()

        loaded = _service(session).get_project(created.id)

        assert loaded.name == "Alpha Portal"


def test_get_project_fails_when_missing() -> None:
    with _session() as session:
        with pytest.raises(NotFoundError):
            _service(session).get_project(999)


def test_update_project_changes_fields() -> None:
    with _session() as session:
        manager_id = _create_user(
            session,
            username="ankit",
            email="ankit@example.test",
            role=Role.MANAGER,
        )
        created = _service(session).create_project(
            name="Alpha Portal",
            description="Original description",
            start_date=date(2026, 3, 1),
            end_date=date(2026, 6, 30),
            status=ProjectStatus.ACTIVE,
            manager_user_id=manager_id,
        )
        session.commit()

        updated = _service(session).update_project(
            created.id,
            name="Alpha Portal v2",
            status=ProjectStatus.ON_HOLD,
        )
        session.commit()

        assert updated.name == "Alpha Portal v2"
        assert updated.status == ProjectStatus.ON_HOLD
        assert updated.description == "Original description"


def test_update_project_fails_when_dates_invalid() -> None:
    with _session() as session:
        manager_id = _create_user(
            session,
            username="ankit",
            email="ankit@example.test",
            role=Role.MANAGER,
        )
        created = _service(session).create_project(
            name="Alpha Portal",
            description=None,
            start_date=date(2026, 3, 1),
            end_date=date(2026, 6, 30),
            status=ProjectStatus.ACTIVE,
            manager_user_id=manager_id,
        )
        session.commit()

        with pytest.raises(ValidationError, match="start date"):
            _service(session).update_project(
                created.id,
                end_date=date(2026, 2, 1),
            )


def test_update_project_fails_when_new_manager_invalid() -> None:
    with _session() as session:
        manager_id = _create_user(
            session,
            username="ankit",
            email="ankit@example.test",
            role=Role.MANAGER,
        )
        user_id = _create_user(
            session,
            username="ravi",
            email="ravi@example.test",
            role=Role.ENGINEER,
        )
        created = _service(session).create_project(
            name="Alpha Portal",
            description=None,
            start_date=date(2026, 3, 1),
            end_date=date(2026, 6, 30),
            status=ProjectStatus.ACTIVE,
            manager_user_id=manager_id,
        )
        session.commit()

        with pytest.raises(ValidationError, match="Manager account"):
            _service(session).update_project(
                created.id,
                manager_user_id=user_id,
            )


def test_update_project_fails_when_missing() -> None:
    with _session() as session:
        with pytest.raises(NotFoundError):
            _service(session).update_project(999, name="Missing Project")


def test_create_project_persists_total_story_points() -> None:
    with _session() as session:
        manager_id = _create_user(
            session,
            username="ankit",
            email="ankit@example.test",
            role=Role.MANAGER,
        )
        created = _service(session).create_project(
            name="Alpha Portal",
            description=None,
            start_date=date(2026, 3, 1),
            end_date=date(2026, 6, 30),
            status=ProjectStatus.ACTIVE,
            manager_user_id=manager_id,
            total_story_points=120,
        )
        session.commit()

        assert created.total_story_points == 120


def test_list_projects_includes_story_point_rollups() -> None:
    with _session() as session:
        manager_id = _create_user(
            session,
            username="ankit",
            email="ankit@example.test",
            role=Role.MANAGER,
        )
        project_service = _service(session)
        milestone_repo = SqlAlchemyMilestoneRepository(session)
        project = project_service.create_project(
            name="Alpha Portal",
            description=None,
            start_date=date(2026, 3, 1),
            end_date=date(2026, 6, 30),
            status=ProjectStatus.ACTIVE,
            manager_user_id=manager_id,
            total_story_points=120,
        )
        milestone_repo.create(
            project_id=project.id,
            title="Design Complete",
            due_date=date(2026, 4, 1),
            status=MilestoneStatus.DONE,
            story_points=20,
        )
        milestone_repo.create(
            project_id=project.id,
            title="Backend API",
            due_date=date(2026, 4, 15),
            status=MilestoneStatus.IN_PROGRESS,
            story_points=40,
        )
        session.commit()

        result = project_service.list_projects()

        assert result.projects[0].story_points_done == 20
        assert result.projects[0].story_points_total == 120


def test_update_project_supports_completed_status_and_story_points() -> None:
    with _session() as session:
        manager_id = _create_user(
            session,
            username="ankit",
            email="ankit@example.test",
            role=Role.MANAGER,
        )
        created = _service(session).create_project(
            name="Alpha Portal",
            description=None,
            start_date=date(2026, 3, 1),
            end_date=date(2026, 6, 30),
            status=ProjectStatus.ACTIVE,
            manager_user_id=manager_id,
            total_story_points=80,
        )
        session.commit()

        updated = _service(session).update_project(
            created.id,
            status=ProjectStatus.COMPLETED,
            total_story_points=100,
        )
        session.commit()

        assert updated.status == ProjectStatus.COMPLETED
        assert updated.total_story_points == 100
