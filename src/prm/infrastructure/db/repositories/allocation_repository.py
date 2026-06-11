"""Allocation persistence via SQLAlchemy."""

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from prm.domain.entities.allocation import Allocation
from prm.domain.enums import AllocationStatus
from prm.domain.exceptions import NotFoundError
from prm.infrastructure.db.models import AllocationModel, ProjectModel


def _to_domain(model: AllocationModel) -> Allocation:
    return Allocation(
        id=model.id,
        user_id=model.user_id,
        project_id=model.project_id,
        utilisation_percent=model.utilisation_percent,
        from_date=model.from_date,
        to_date=model.to_date,
        status=model.status,
        created_by_user_id=model.created_by_user_id,
    )


class SqlAlchemyAllocationRepository:
    """Load and update allocations from the allocations table."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def find_by_id(self, allocation_id: int) -> Allocation | None:
        model = self._session.get(AllocationModel, allocation_id)
        return _to_domain(model) if model is not None else None

    def find_active_by_user(self, user_id: int) -> list[Allocation]:
        models = self._session.scalars(
            select(AllocationModel)
            .where(AllocationModel.user_id == user_id)
            .where(AllocationModel.status == AllocationStatus.ACTIVE)
            .order_by(AllocationModel.id)
        ).all()
        return [_to_domain(model) for model in models]

    def list_by_user(self, user_id: int) -> list[Allocation]:
        models = self._session.scalars(
            select(AllocationModel)
            .where(AllocationModel.user_id == user_id)
            .order_by(AllocationModel.id)
        ).all()
        return [_to_domain(model) for model in models]

    def find_overlapping(
        self,
        user_id: int,
        date_from: date,
        date_to: date | None,
        *,
        exclude_allocation_id: int | None = None,
    ) -> list[Allocation]:
        active = self.find_active_by_user(user_id)
        return [
            allocation
            for allocation in active
            if (exclude_allocation_id is None or allocation.id != exclude_allocation_id)
            and allocation.overlaps_period(date_from, date_to)
        ]

    def list_active(
        self,
        *,
        user_id: int | None = None,
        project_id: int | None = None,
    ) -> list[Allocation]:
        stmt = (
            select(AllocationModel)
            .where(AllocationModel.status == AllocationStatus.ACTIVE)
            .order_by(AllocationModel.id)
        )
        if user_id is not None:
            stmt = stmt.where(AllocationModel.user_id == user_id)
        if project_id is not None:
            stmt = stmt.where(AllocationModel.project_id == project_id)
        models = self._session.scalars(stmt).all()
        return [_to_domain(model) for model in models]

    def list_active_for_manager(self, manager_user_id: int) -> list[Allocation]:
        models = self._session.scalars(
            select(AllocationModel)
            .join(ProjectModel, AllocationModel.project_id == ProjectModel.id)
            .where(ProjectModel.manager_user_id == manager_user_id)
            .where(AllocationModel.status == AllocationStatus.ACTIVE)
            .order_by(AllocationModel.id)
        ).all()
        return [_to_domain(model) for model in models]

    def create(
        self,
        *,
        user_id: int,
        project_id: int,
        utilisation_percent: int,
        from_date: date,
        to_date: date | None,
        created_by_user_id: int,
    ) -> Allocation:
        model = AllocationModel(
            user_id=user_id,
            project_id=project_id,
            utilisation_percent=utilisation_percent,
            from_date=from_date,
            to_date=to_date,
            status=AllocationStatus.ACTIVE,
            created_by_user_id=created_by_user_id,
        )
        self._session.add(model)
        self._session.flush()
        self._session.refresh(model)
        return _to_domain(model)

    def end_by_id(self, allocation_id: int, *, as_of: date) -> Allocation:
        model = self._session.get(AllocationModel, allocation_id)
        if model is None:
            raise NotFoundError(f"Allocation {allocation_id} not found.")
        if model.status != AllocationStatus.ACTIVE:
            raise NotFoundError(f"Allocation {allocation_id} is not active.")

        model.to_date = as_of
        model.status = AllocationStatus.ENDED
        self._session.flush()
        self._session.refresh(model)
        return _to_domain(model)

    def end_active_for_user(self, user_id: int, *, as_of: date) -> list[Allocation]:
        models = list(
            self._session.scalars(
                select(AllocationModel)
                .where(AllocationModel.user_id == user_id)
                .where(AllocationModel.status == AllocationStatus.ACTIVE)
                .order_by(AllocationModel.id)
            ).all()
        )
        if not models:
            return []

        for model in models:
            model.to_date = as_of
            model.status = AllocationStatus.ENDED

        self._session.flush()
        return [_to_domain(model) for model in models]
