"""Project persistence via SQLAlchemy."""

from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from prm.domain.entities.project import Project
from prm.domain.enums import ProjectHealthStatus, ProjectStatus
from prm.domain.exceptions import NotFoundError
from prm.infrastructure.db.models import ProjectModel


def _to_domain(model: ProjectModel) -> Project:
    return Project(
        id=model.id,
        name=model.name,
        description=model.description,
        start_date=model.start_date,
        end_date=model.end_date,
        status=model.status,
        manager_user_id=model.manager_user_id,
        total_story_points=model.total_story_points,
        health_status=model.health_status,
        health_computed_at=model.health_computed_at,
        last_at_risk_email_sent_at=model.last_at_risk_email_sent_at,
    )


class SqlAlchemyProjectRepository:
    """Load and update projects from the projects table."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def find_by_id(self, project_id: int) -> Project | None:
        model = self._session.get(ProjectModel, project_id)
        return _to_domain(model) if model is not None else None

    def list_all(
        self,
        *,
        status: ProjectStatus | None = None,
    ) -> list[Project]:
        stmt = select(ProjectModel)
        if status is not None:
            stmt = stmt.where(ProjectModel.status == status)
        models = self._session.scalars(stmt.order_by(ProjectModel.id)).all()
        return [_to_domain(model) for model in models]

    def list_by_manager_user_id(self, manager_user_id: int) -> list[Project]:
        models = self._session.scalars(
            select(ProjectModel)
            .where(ProjectModel.manager_user_id == manager_user_id)
            .order_by(ProjectModel.id)
        ).all()
        return [_to_domain(model) for model in models]

    def create(
        self,
        *,
        name: str,
        description: str | None,
        start_date: date,
        end_date: date | None,
        status: ProjectStatus,
        manager_user_id: int,
        total_story_points: int = 0,
    ) -> Project:
        model = ProjectModel(
            name=name,
            description=description,
            start_date=start_date,
            end_date=end_date,
            status=status,
            manager_user_id=manager_user_id,
            total_story_points=total_story_points,
            health_status=ProjectHealthStatus.ON_TRACK,
        )
        self._session.add(model)
        self._session.flush()
        self._session.refresh(model)
        return _to_domain(model)

    def update(
        self,
        project_id: int,
        *,
        name: str | None = None,
        description: str | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
        status: ProjectStatus | None = None,
        manager_user_id: int | None = None,
        total_story_points: int | None = None,
    ) -> Project:
        model = self._session.get(ProjectModel, project_id)
        if model is None:
            raise NotFoundError(f"Project {project_id} not found.")

        if name is not None:
            model.name = name
        if description is not None:
            model.description = description
        if start_date is not None:
            model.start_date = start_date
        if end_date is not None:
            model.end_date = end_date
        if status is not None:
            model.status = status
        if manager_user_id is not None:
            model.manager_user_id = manager_user_id
        if total_story_points is not None:
            model.total_story_points = total_story_points

        self._session.flush()
        self._session.refresh(model)
        return _to_domain(model)

    def update_health(
        self,
        project_id: int,
        *,
        health_status: ProjectHealthStatus,
        health_computed_at: datetime,
    ) -> Project:
        model = self._session.get(ProjectModel, project_id)
        if model is None:
            raise NotFoundError(f"Project {project_id} not found.")

        model.health_status = health_status
        model.health_computed_at = health_computed_at
        self._session.flush()
        self._session.refresh(model)
        return _to_domain(model)

    def update_last_at_risk_email_sent(
        self,
        project_id: int,
        sent_at: datetime,
    ) -> Project:
        model = self._session.get(ProjectModel, project_id)
        if model is None:
            raise NotFoundError(f"Project {project_id} not found.")

        model.last_at_risk_email_sent_at = sent_at
        self._session.flush()
        self._session.refresh(model)
        return _to_domain(model)

    def clear_last_at_risk_email_sent(self, project_id: int) -> Project:
        model = self._session.get(ProjectModel, project_id)
        if model is None:
            raise NotFoundError(f"Project {project_id} not found.")

        model.last_at_risk_email_sent_at = None
        self._session.flush()
        self._session.refresh(model)
        return _to_domain(model)
