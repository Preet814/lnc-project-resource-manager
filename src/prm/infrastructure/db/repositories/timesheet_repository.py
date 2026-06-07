"""Timesheet read access for manager dashboard drill-down."""

from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from prm.domain.enums import ActivityTag
from prm.infrastructure.db.models import TimesheetWeekModel


def _format_activity_tag(tag: ActivityTag) -> str:
    return tag.value.replace("_", " ").title()


class SqlAlchemyTimesheetRepository:
    """Read recent activity tags submitted by an employee."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def list_recent_activity_tags(
        self,
        employee_id: int,
        *,
        weeks: int = 4,
        as_of: date | None = None,
    ) -> list[str]:
        reference = as_of or date.today()
        cutoff = reference - timedelta(weeks=weeks)
        weeks_models = self._session.scalars(
            select(TimesheetWeekModel)
            .where(TimesheetWeekModel.employee_id == employee_id)
            .where(TimesheetWeekModel.week_start_date >= cutoff)
            .order_by(TimesheetWeekModel.week_start_date.desc())
        ).all()

        seen: set[str] = set()
        tags: list[str] = []
        for week in weeks_models:
            for entry in week.entries:
                for tag in entry.activity_tags:
                    label = _format_activity_tag(tag)
                    if label not in seen:
                        seen.add(label)
                        tags.append(label)
        return tags
