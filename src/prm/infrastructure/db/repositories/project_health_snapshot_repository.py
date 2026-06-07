"""Project health snapshot persistence via SQLAlchemy."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from prm.domain.entities.project_health_snapshot import ProjectHealthSnapshot
from prm.infrastructure.db.models import ProjectHealthSnapshotModel


def _to_domain(model: ProjectHealthSnapshotModel) -> ProjectHealthSnapshot:
    return ProjectHealthSnapshot(
        id=model.id,
        project_id=model.project_id,
        status=model.status,
        risk_flags=tuple(model.risk_flags),
        computed_at=model.computed_at,
    )


class SqlAlchemyProjectHealthSnapshotRepository:
    """Load project health snapshots from the project_health_snapshots table."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def find_latest_for_project(self, project_id: int) -> ProjectHealthSnapshot | None:
        model = self._session.scalar(
            select(ProjectHealthSnapshotModel)
            .where(ProjectHealthSnapshotModel.project_id == project_id)
            .order_by(ProjectHealthSnapshotModel.computed_at.desc())
            .limit(1)
        )
        return _to_domain(model) if model is not None else None
