"""Unit tests for ProjectMilestoneService."""

from datetime import date

import pytest
from sqlalchemy.orm import Session

from prm.application.project_management_service import ProjectManagementService
from prm.application.project_milestone_service import ProjectMilestoneService
from prm.application.user_management_service import UserManagementService
from prm.domain.enums import MilestoneStatus, ProjectStatus, Role
from prm.domain.exceptions import NotFoundError, ValidationError
from prm.infrastructure.db.repositories import (
    SqlAlchemyMilestoneRepository,
    SqlAlchemyProjectRepository,
    SqlAlchemyUserRepository,
)
from prm.infrastructure.security.password import BcryptPasswordHasher
from tests.unit.engineer_fixtures import create_memory_session, seed_rbac


def _session() -> Session:
    return create_memory_session(include_project=True)


def _milestone_service(session: Session) -> ProjectMilestoneService:
    return ProjectMilestoneService(
        project_repository=SqlAlchemyProjectRepository(session),
        milestone_repository=SqlAlchemyMilestoneRepository(session),
    )


def _project_service(session: Session) -> ProjectManagementService:
    return ProjectManagementService(
        project_repository=SqlAlchemyProjectRepository(session),
        user_repository=SqlAlchemyUserRepository(session),
        milestone_repository=SqlAlchemyMilestoneRepository(session),
    )


def _create_project(session: Session) -> int:
    seed_rbac(session)
    manager = UserManagementService(
        user_repository=SqlAlchemyUserRepository(session),
        password_hasher=BcryptPasswordHasher(),
    ).create_user(
        full_name="Ankit Shah",
        email="ankit@example.test",
        username="ankit",
        temporary_password="TempPass1",
        role=Role.MANAGER,
    )
    session.flush()
    project = _project_service(session).create_project(
        name="Alpha Portal",
        description="Customer portal rewrite",
        start_date=date(2026, 3, 1),
        end_date=date(2026, 6, 30),
        status=ProjectStatus.ACTIVE,
        manager_user_id=manager.id,
    )
    session.flush()
    return project.id


def test_list_milestones_returns_milestone_details() -> None:
    with _session() as session:
        project_id = _create_project(session)
        service = _milestone_service(session)
        service.add_milestone(
            project_id,
            title="Design Complete",
            due_date=date(2026, 4, 1),
            status=MilestoneStatus.DONE,
        )
        service.add_milestone(
            project_id,
            title="Backend API",
            due_date=date(2026, 4, 15),
            status=MilestoneStatus.IN_PROGRESS,
        )
        session.commit()

        milestones = service.list_milestones(project_id)

        assert len(milestones.milestones) == 2
        assert milestones.milestones[0].title == "Design Complete"
        assert milestones.milestones[0].status == MilestoneStatus.DONE
        assert milestones.milestones[1].title == "Backend API"
        assert milestones.milestones[1].status == MilestoneStatus.IN_PROGRESS


def test_add_milestone_creates_milestone_with_defaults() -> None:
    with _session() as session:
        project_id = _create_project(session)
        service = _milestone_service(session)

        added = service.add_milestone(
            project_id,
            title="Backend API",
            due_date=date(2026, 4, 15),
        )
        session.commit()

        assert added.title == "Backend API"
        assert added.status == MilestoneStatus.NOT_STARTED
        assert added.sequence_order == 1


def test_add_milestone_fails_when_title_blank() -> None:
    with _session() as session:
        project_id = _create_project(session)
        with pytest.raises(ValidationError, match="Milestone title is required"):
            _milestone_service(session).add_milestone(
                project_id,
                title="   ",
                due_date=date(2026, 4, 15),
            )


def test_add_milestone_fails_when_project_missing() -> None:
    with _session() as session:
        with pytest.raises(NotFoundError):
            _milestone_service(session).add_milestone(
                999,
                title="Backend API",
                due_date=date(2026, 4, 15),
            )


def test_update_milestone_changes_status() -> None:
    with _session() as session:
        project_id = _create_project(session)
        service = _milestone_service(session)
        added = service.add_milestone(
            project_id,
            title="Backend API",
            due_date=date(2026, 4, 15),
        )
        session.commit()

        updated = service.update_milestone(
            project_id,
            added.milestone_id,
            status=MilestoneStatus.IN_PROGRESS,
        )
        session.commit()

        assert updated.status == MilestoneStatus.IN_PROGRESS
        assert updated.title == "Backend API"


def test_update_milestone_fails_when_title_blank() -> None:
    with _session() as session:
        project_id = _create_project(session)
        service = _milestone_service(session)
        added = service.add_milestone(
            project_id,
            title="Backend API",
            due_date=date(2026, 4, 15),
        )
        session.commit()

        with pytest.raises(ValidationError, match="Milestone title is required"):
            service.update_milestone(
                project_id,
                added.milestone_id,
                title="   ",
            )


def test_update_milestone_fails_when_milestone_not_for_project() -> None:
    with _session() as session:
        first_project_id = _create_project(session)
        seed_rbac(session)
        manager = UserManagementService(
            user_repository=SqlAlchemyUserRepository(session),
            password_hasher=BcryptPasswordHasher(),
        ).create_user(
            full_name="Neha Joshi",
            email="neha@example.test",
            username="neha",
            temporary_password="TempPass1",
            role=Role.MANAGER,
        )
        session.flush()
        second_project = _project_service(session).create_project(
            name="Beta CRM",
            description=None,
            start_date=date(2026, 4, 1),
            end_date=date(2026, 8, 15),
            status=ProjectStatus.ACTIVE,
            manager_user_id=manager.id,
        )
        service = _milestone_service(session)
        milestone = service.add_milestone(
            first_project_id,
            title="Backend API",
            due_date=date(2026, 4, 15),
        )
        session.commit()

        with pytest.raises(NotFoundError):
            service.update_milestone(
                second_project.id,
                milestone.milestone_id,
                status=MilestoneStatus.DONE,
            )


def test_list_milestones_fails_when_project_missing() -> None:
    with _session() as session:
        with pytest.raises(NotFoundError):
            _milestone_service(session).list_milestones(999)


def test_list_milestones_returns_story_point_totals() -> None:
    with _session() as session:
        project_id = _create_project(session)
        service = _milestone_service(session)
        _project_service(session).update_project(
            project_id,
            total_story_points=120,
        )
        service.add_milestone(
            project_id,
            title="Design Complete",
            due_date=date(2026, 4, 1),
            status=MilestoneStatus.DONE,
            story_points=20,
        )
        service.add_milestone(
            project_id,
            title="Backend API",
            due_date=date(2026, 4, 15),
            status=MilestoneStatus.IN_PROGRESS,
            story_points=40,
        )
        session.commit()

        result = service.list_milestones(project_id)

        assert result.total_story_points == 120
        assert result.completed_story_points == 20
        assert result.remaining_story_points == 100
        assert result.milestones[0].story_points == 20
