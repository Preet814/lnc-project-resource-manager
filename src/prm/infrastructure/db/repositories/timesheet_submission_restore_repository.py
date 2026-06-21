"""Persistence for manager timesheet submission restores."""

from datetime import UTC, date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from prm.infrastructure.db.models import TimesheetSubmissionRestoreModel


class SqlAlchemyTimesheetSubmissionRestoreRepository:
    """Read and write timesheet submission restore records."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def find_by_user_and_week(
        self,
        user_id: int,
        week_start_date: date,
    ) -> bool:
        model = self._session.scalar(
            select(TimesheetSubmissionRestoreModel)
            .where(TimesheetSubmissionRestoreModel.user_id == user_id)
            .where(TimesheetSubmissionRestoreModel.week_start_date == week_start_date)
        )
        return model is not None

    def create(
        self,
        *,
        user_id: int,
        week_start_date: date,
        restored_by_user_id: int,
        restored_at: datetime | None = None,
    ) -> None:
        self._session.add(
            TimesheetSubmissionRestoreModel(
                user_id=user_id,
                week_start_date=week_start_date,
                restored_by_user_id=restored_by_user_id,
                restored_at=restored_at or datetime.now(UTC),
            )
        )
        self._session.flush()
