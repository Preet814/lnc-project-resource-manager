"""Unit tests for SQLAlchemy milestone repository."""

from datetime import datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from prm.domain.enums import MilestoneStatus, ProjectStatus, Role
from prm.domain.exceptions import NotFoundError
from prm.infrastructure.db.models import MilestoneModel, ProjectModel, UserModel
from prm.infrastructure.db.repositories import (
    SqlAlchemyMilestoneRepository,
    SqlAlchemyProjectRepository,
    SqlAlchemyUserRepository,
)
from prm.infrastructure.security.password import BcryptPasswordHasher


def _session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    UserModel.__table__.create(engine, checkfirst=True)
    ProjectModel.__table__.create(engine, checkfirst=True)
    MilestoneModel.__table__.create(engine, checkfirst=True)
    return Session(engine)


def _seed_project(session: Session) -> int:
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
        start_date=datetime(2026, 3, 1).date(),
        end_date=datetime(2026, 6, 30).date(),
        status=ProjectStatus.ACTIVE,
        manager_user_id=manager.id,
    )
    session.flush()
    return project.id


def test_create_persists_milestone_with_default_status() -> None:
    with _session() as session:
        project_id = _seed_project(session)
        repo = SqlAlchemyMilestoneRepository(session)

        created = repo.create(
            project_id=project_id,
            title="Backend API",
            due_date=datetime(2026, 4, 15).date(),
        )
        session.commit()

        assert created.project_id == project_id
        assert created.title == "Backend API"
        assert created.status == MilestoneStatus.NOT_STARTED
        assert created.sequence_order == 1


def test_create_auto_assigns_sequence_order() -> None:
    with _session() as session:
        project_id = _seed_project(session)
        repo = SqlAlchemyMilestoneRepository(session)
        first = repo.create(
            project_id=project_id,
            title="Design Complete",
            due_date=datetime(2026, 4, 1).date(),
            sequence_order=1,
        )
        second = repo.create(
            project_id=project_id,
            title="Backend API",
            due_date=datetime(2026, 4, 15).date(),
        )
        session.commit()

        assert first.sequence_order == 1
        assert second.sequence_order == 2


def test_list_for_project_returns_milestones_ordered_by_sequence() -> None:
    with _session() as session:
        project_id = _seed_project(session)
        repo = SqlAlchemyMilestoneRepository(session)
        second = repo.create(
            project_id=project_id,
            title="Backend API",
            due_date=datetime(2026, 4, 15).date(),
            sequence_order=2,
        )
        first = repo.create(
            project_id=project_id,
            title="Design Complete",
            due_date=datetime(2026, 4, 1).date(),
            sequence_order=1,
        )
        session.commit()

        milestones = repo.list_for_project(project_id)

        assert len(milestones) == 2
        assert milestones[0].id == first.id
        assert milestones[1].id == second.id


def test_find_by_id_returns_domain_milestone() -> None:
    with _session() as session:
        project_id = _seed_project(session)
        repo = SqlAlchemyMilestoneRepository(session)
        created = repo.create(
            project_id=project_id,
            title="Backend API",
            due_date=datetime(2026, 4, 15).date(),
        )
        session.commit()

        milestone = repo.find_by_id(created.id)

        assert milestone is not None
        assert milestone.title == "Backend API"


def test_find_by_project_and_id_returns_milestone() -> None:
    with _session() as session:
        project_id = _seed_project(session)
        repo = SqlAlchemyMilestoneRepository(session)
        created = repo.create(
            project_id=project_id,
            title="Backend API",
            due_date=datetime(2026, 4, 15).date(),
        )
        session.commit()

        milestone = repo.find_by_project_and_id(project_id, created.id)

        assert milestone is not None
        assert milestone.id == created.id


def test_find_returns_none_when_missing() -> None:
    with _session() as session:
        project_id = _seed_project(session)
        repo = SqlAlchemyMilestoneRepository(session)

        assert repo.find_by_id(999) is None
        assert repo.find_by_project_and_id(project_id, 999) is None


def test_update_changes_provided_fields() -> None:
    with _session() as session:
        project_id = _seed_project(session)
        repo = SqlAlchemyMilestoneRepository(session)
        created = repo.create(
            project_id=project_id,
            title="Backend API",
            due_date=datetime(2026, 4, 15).date(),
        )
        session.commit()

        updated = repo.update(
            created.id,
            status=MilestoneStatus.IN_PROGRESS,
        )
        session.commit()

        assert updated.status == MilestoneStatus.IN_PROGRESS
        assert updated.title == "Backend API"


def test_update_raises_when_milestone_missing() -> None:
    with _session() as session:
        repo = SqlAlchemyMilestoneRepository(session)
        with pytest.raises(NotFoundError):
            repo.update(999, status=MilestoneStatus.DONE)
