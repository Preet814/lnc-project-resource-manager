"""Milestone persistence via SQLAlchemy."""

from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from prm.domain.entities.milestone import Milestone
from prm.domain.enums import MilestoneStatus
from prm.domain.exceptions import NotFoundError
from prm.infrastructure.db.models import MilestoneModel


def _to_domain(model: MilestoneModel) -> Milestone:
    return Milestone(
        id=model.id,
        project_id=model.project_id,
        title=model.title,
        due_date=model.due_date,
        status=model.status,
        sequence_order=model.sequence_order,
    )


class SqlAlchemyMilestoneRepository:
    """Load and update project milestones."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def list_for_project(self, project_id: int) -> list[Milestone]:
        models = self._session.scalars(
            select(MilestoneModel)
            .where(MilestoneModel.project_id == project_id)
            .order_by(MilestoneModel.sequence_order, MilestoneModel.id)
        ).all()
        return [_to_domain(model) for model in models]

    def find_by_id(self, milestone_id: int) -> Milestone | None:
        model = self._session.get(MilestoneModel, milestone_id)
        return _to_domain(model) if model is not None else None

    def find_by_project_and_id(
        self, project_id: int, milestone_id: int
    ) -> Milestone | None:
        model = self._session.scalar(
            select(MilestoneModel).where(
                MilestoneModel.project_id == project_id,
                MilestoneModel.id == milestone_id,
            )
        )
        return _to_domain(model) if model is not None else None

    def create(
        self,
        *,
        project_id: int,
        title: str,
        due_date: date,
        status: MilestoneStatus = MilestoneStatus.NOT_STARTED,
        sequence_order: int | None = None,
    ) -> Milestone:
        resolved_sequence = sequence_order
        if resolved_sequence is None:
            max_order = self._session.scalar(
                select(func.max(MilestoneModel.sequence_order)).where(
                    MilestoneModel.project_id == project_id
                )
            )
            resolved_sequence = (max_order or 0) + 1

        model = MilestoneModel(
            project_id=project_id,
            title=title,
            due_date=due_date,
            status=status,
            sequence_order=resolved_sequence,
        )
        self._session.add(model)
        self._session.flush()
        self._session.refresh(model)
        return _to_domain(model)

    def update(
        self,
        milestone_id: int,
        *,
        title: str | None = None,
        due_date: date | None = None,
        status: MilestoneStatus | None = None,
        sequence_order: int | None = None,
    ) -> Milestone:
        model = self._session.get(MilestoneModel, milestone_id)
        if model is None:
            raise NotFoundError(f"Milestone {milestone_id} not found.")

        if title is not None:
            model.title = title
        if due_date is not None:
            model.due_date = due_date
        if status is not None:
            model.status = status
        if sequence_order is not None:
            model.sequence_order = sequence_order

        self._session.flush()
        self._session.refresh(model)
        return _to_domain(model)
