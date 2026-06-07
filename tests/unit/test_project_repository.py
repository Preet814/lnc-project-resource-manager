"""Unit tests for SQLAlchemy project repository."""

from datetime import datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from prm.domain.enums import ProjectHealthStatus, ProjectStatus, Role
from prm.domain.exceptions import NotFoundError
from prm.infrastructure.db.models import ProjectModel, UserModel
from prm.infrastructure.db.repositories import SqlAlchemyProjectRepository, SqlAlchemyUserRepository
from prm.infrastructure.security.password import BcryptPasswordHasher


def _session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    UserModel.__table__.create(engine, checkfirst=True)
    ProjectModel.__table__.create(engine, checkfirst=True)
    return Session(engine)


def _create_manager(session: Session, *, username: str, email: str) -> int:
    repo = SqlAlchemyUserRepository(session)
    hasher = BcryptPasswordHasher()
    user = repo.create(
        full_name=f"{username} Name",
        username=username,
        email=email,
        password_hash=hasher.hash("TempPass1"),
        role=Role.MANAGER,
    )
    session.flush()
    return user.id


def _create_project(
    session: Session,
    *,
    manager_user_id: int,
    name: str = "Alpha Portal",
    status: ProjectStatus = ProjectStatus.ACTIVE,
) -> int:
    repo = SqlAlchemyProjectRepository(session)
    project = repo.create(
        name=name,
        description="Customer portal rewrite",
        start_date=datetime(2026, 3, 1).date(),
        end_date=datetime(2026, 6, 30).date(),
        status=status,
        manager_user_id=manager_user_id,
    )
    session.flush()
    return project.id


def test_create_persists_project_with_default_health() -> None:
    with _session() as session:
        manager_id = _create_manager(session, username="ankit", email="ankit@example.test")
        repo = SqlAlchemyProjectRepository(session)

        created = repo.create(
            name="Alpha Portal",
            description="Customer portal rewrite",
            start_date=datetime(2026, 3, 1).date(),
            end_date=datetime(2026, 6, 30).date(),
            status=ProjectStatus.ACTIVE,
            manager_user_id=manager_id,
        )
        session.commit()

        assert created.name == "Alpha Portal"
        assert created.status == ProjectStatus.ACTIVE
        assert created.manager_user_id == manager_id
        assert created.health_status == ProjectHealthStatus.ON_TRACK
        assert created.health_computed_at is None


def test_find_by_id_returns_domain_project() -> None:
    with _session() as session:
        manager_id = _create_manager(session, username="ankit", email="ankit@example.test")
        project_id = _create_project(session, manager_user_id=manager_id)
        repo = SqlAlchemyProjectRepository(session)

        project = repo.find_by_id(project_id)

        assert project is not None
        assert project.id == project_id
        assert project.name == "Alpha Portal"


def test_find_returns_none_when_missing() -> None:
    with _session() as session:
        repo = SqlAlchemyProjectRepository(session)

        assert repo.find_by_id(999) is None


def test_list_all_returns_projects_ordered_by_id() -> None:
    with _session() as session:
        manager_id = _create_manager(session, username="ankit", email="ankit@example.test")
        repo = SqlAlchemyProjectRepository(session)
        first_id = repo.create(
            name="Alpha Portal",
            description=None,
            start_date=datetime(2026, 3, 1).date(),
            end_date=datetime(2026, 6, 30).date(),
            status=ProjectStatus.ACTIVE,
            manager_user_id=manager_id,
        ).id
        second_id = repo.create(
            name="Beta CRM",
            description=None,
            start_date=datetime(2026, 4, 1).date(),
            end_date=datetime(2026, 8, 15).date(),
            status=ProjectStatus.PLANNED,
            manager_user_id=manager_id,
        ).id
        session.commit()

        projects = repo.list_all()

        assert len(projects) == 2
        assert projects[0].id == first_id
        assert projects[1].id == second_id


def test_list_all_filters_by_status() -> None:
    with _session() as session:
        manager_id = _create_manager(session, username="ankit", email="ankit@example.test")
        repo = SqlAlchemyProjectRepository(session)
        active = repo.create(
            name="Alpha Portal",
            description=None,
            start_date=datetime(2026, 3, 1).date(),
            end_date=datetime(2026, 6, 30).date(),
            status=ProjectStatus.ACTIVE,
            manager_user_id=manager_id,
        )
        repo.create(
            name="Delta Migrate",
            description=None,
            start_date=datetime(2026, 5, 1).date(),
            end_date=datetime(2026, 9, 30).date(),
            status=ProjectStatus.PLANNED,
            manager_user_id=manager_id,
        )
        session.commit()

        active_projects = repo.list_all(status=ProjectStatus.ACTIVE)

        assert len(active_projects) == 1
        assert active_projects[0].id == active.id


def test_update_changes_provided_fields() -> None:
    with _session() as session:
        manager_id = _create_manager(session, username="ankit", email="ankit@example.test")
        project_id = _create_project(session, manager_user_id=manager_id)
        repo = SqlAlchemyProjectRepository(session)

        updated = repo.update(
            project_id,
            name="Alpha Portal v2",
            status=ProjectStatus.ON_HOLD,
        )
        session.commit()

        assert updated.name == "Alpha Portal v2"
        assert updated.status == ProjectStatus.ON_HOLD
        assert updated.description == "Customer portal rewrite"


def test_update_raises_when_project_missing() -> None:
    with _session() as session:
        repo = SqlAlchemyProjectRepository(session)
        with pytest.raises(NotFoundError):
            repo.update(999, name="Missing Project")


def test_list_by_manager_user_id_returns_only_owned_projects() -> None:
    with _session() as session:
        manager_a = _create_manager(session, username="ankit", email="ankit@example.test")
        manager_b = _create_manager(session, username="rohan", email="rohan@example.test")
        repo = SqlAlchemyProjectRepository(session)
        owned_id = repo.create(
            name="Alpha Portal",
            description=None,
            start_date=datetime(2026, 3, 1).date(),
            end_date=datetime(2026, 6, 30).date(),
            status=ProjectStatus.ACTIVE,
            manager_user_id=manager_a,
        ).id
        repo.create(
            name="Beta CRM",
            description=None,
            start_date=datetime(2026, 4, 1).date(),
            end_date=datetime(2026, 8, 15).date(),
            status=ProjectStatus.ACTIVE,
            manager_user_id=manager_b,
        )
        session.commit()

        projects = repo.list_by_manager_user_id(manager_a)

        assert len(projects) == 1
        assert projects[0].id == owned_id
        assert projects[0].name == "Alpha Portal"


def test_list_by_manager_user_id_returns_empty_when_none() -> None:
    with _session() as session:
        manager_id = _create_manager(session, username="ankit", email="ankit@example.test")
        session.commit()
        repo = SqlAlchemyProjectRepository(session)

        assert repo.list_by_manager_user_id(manager_id) == []
