"""Unit tests for SQLAlchemy project health snapshot repository."""

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from prm.domain.enums import ProjectHealthStatus, ProjectStatus, Role
from prm.infrastructure.db.models import ProjectHealthSnapshotModel
from prm.infrastructure.db.repositories import (
    SqlAlchemyProjectHealthSnapshotRepository,
    SqlAlchemyProjectRepository,
)
from tests.unit.engineer_fixtures import create_memory_session, create_user


def _session() -> Session:
    return create_memory_session(include_project=True)


def _seed_project(session: Session) -> int:
    manager_id = create_user(
        session,
        full_name="Ankit Shah",
        username="ankit",
        email="ankit@example.test",
        role=Role.MANAGER,
    )
    project_repo = SqlAlchemyProjectRepository(session)
    project = project_repo.create(
        name="Alpha Portal",
        description="Customer portal rewrite",
        start_date=datetime(2026, 3, 1).date(),
        end_date=datetime(2026, 6, 30).date(),
        status=ProjectStatus.ACTIVE,
        manager_user_id=manager_id,
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


def test_save_persists_snapshot_and_becomes_latest() -> None:
    with _session() as session:
        project_id = _seed_project(session)
        repo = SqlAlchemyProjectHealthSnapshotRepository(session)
        computed_at = datetime(2026, 5, 12, 10, 0, tzinfo=UTC)

        saved = repo.save(
            project_id=project_id,
            status=ProjectHealthStatus.AT_RISK,
            risk_flags=(
                "Backend API milestone is 5 days overdue",
                "Resources are correctly allocated",
            ),
            computed_at=computed_at,
        )
        session.commit()

        assert saved.id > 0
        assert saved.project_id == project_id
        assert saved.status == ProjectHealthStatus.AT_RISK
        assert saved.risk_flags == (
            "Backend API milestone is 5 days overdue",
            "Resources are correctly allocated",
        )
        assert saved.computed_at == computed_at.replace(tzinfo=None)

        latest = repo.find_latest_for_project(project_id)
        assert latest is not None
        assert latest.id == saved.id
