"""Unit tests for SQLAlchemy project health snapshot repository."""

from datetime import UTC, datetime

from sqlalchemy import JSON, create_engine
from sqlalchemy.orm import Session

from prm.domain.enums import ProjectHealthStatus, ProjectStatus, Role
from prm.infrastructure.db.models import ProjectHealthSnapshotModel, ProjectModel, UserModel
from prm.infrastructure.db.repositories import (
    SqlAlchemyProjectHealthSnapshotRepository,
    SqlAlchemyProjectRepository,
    SqlAlchemyUserRepository,
)
from prm.infrastructure.security.password import BcryptPasswordHasher


def _session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    UserModel.__table__.create(engine, checkfirst=True)
    ProjectModel.__table__.create(engine, checkfirst=True)
    ProjectHealthSnapshotModel.__table__.c.risk_flags.type = JSON()
    ProjectHealthSnapshotModel.__table__.create(engine, checkfirst=True)
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


def test_find_latest_for_project_returns_most_recent_snapshot() -> None:
    with _session() as session:
        project_id = _seed_project(session)
        session.add(
            ProjectHealthSnapshotModel(
                project_id=project_id,
                status=ProjectHealthStatus.ATTENTION,
                risk_flags=["Earlier flag"],
                computed_at=datetime(2026, 5, 10, 8, 0, tzinfo=UTC),
            )
        )
        session.add(
            ProjectHealthSnapshotModel(
                project_id=project_id,
                status=ProjectHealthStatus.AT_RISK,
                risk_flags=["Backend API milestone is 5 days overdue"],
                computed_at=datetime(2026, 5, 12, 10, 0, tzinfo=UTC),
            )
        )
        session.commit()
        repo = SqlAlchemyProjectHealthSnapshotRepository(session)

        snapshot = repo.find_latest_for_project(project_id)

        assert snapshot is not None
        assert snapshot.status == ProjectHealthStatus.AT_RISK
        assert snapshot.risk_flags == ("Backend API milestone is 5 days overdue",)


def test_find_latest_for_project_returns_none_when_missing() -> None:
    with _session() as session:
        project_id = _seed_project(session)
        session.commit()
        repo = SqlAlchemyProjectHealthSnapshotRepository(session)

        assert repo.find_latest_for_project(project_id) is None
