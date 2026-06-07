"""Allocation persistence via SQLAlchemy."""

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from prm.domain.entities.allocation import Allocation
from prm.domain.enums import AllocationStatus
from prm.infrastructure.db.models import AllocationModel


def _to_domain(model: AllocationModel) -> Allocation:
    return Allocation(
        id=model.id,
        employee_id=model.employee_id,
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

    def find_active_by_employee(self, employee_id: int) -> list[Allocation]:
        models = self._session.scalars(
            select(AllocationModel)
            .where(AllocationModel.employee_id == employee_id)
            .where(AllocationModel.status == AllocationStatus.ACTIVE)
            .order_by(AllocationModel.id)
        ).all()
        return [_to_domain(model) for model in models]

    def list_active(
        self,
        *,
        employee_id: int | None = None,
        project_id: int | None = None,
    ) -> list[Allocation]:
        stmt = (
            select(AllocationModel)
            .where(AllocationModel.status == AllocationStatus.ACTIVE)
            .order_by(AllocationModel.id)
        )
        if employee_id is not None:
            stmt = stmt.where(AllocationModel.employee_id == employee_id)
        if project_id is not None:
            stmt = stmt.where(AllocationModel.project_id == project_id)
        models = self._session.scalars(stmt).all()
        return [_to_domain(model) for model in models]

    def end_active_for_employee(self, employee_id: int, *, as_of: date) -> list[Allocation]:
        models = list(
            self._session.scalars(
                select(AllocationModel)
                .where(AllocationModel.employee_id == employee_id)
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
