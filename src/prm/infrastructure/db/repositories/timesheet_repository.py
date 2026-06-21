"""Timesheet persistence for manager views and employee submission."""

from datetime import date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from prm.domain.entities.timesheet import NewTimesheetEntry, TimesheetEntry, TimesheetWeek
from prm.domain.enums import ActivityTag, TimesheetWeekStatus
from prm.infrastructure.db.models import TimesheetEntryModel, TimesheetWeekModel


def _format_activity_tag(tag: ActivityTag | str) -> str:
    raw = tag.value if isinstance(tag, ActivityTag) else tag
    return raw.replace("_", " ").title()


def _coerce_activity_tag(tag: ActivityTag | str) -> ActivityTag:
    if isinstance(tag, ActivityTag):
        return tag
    return ActivityTag(tag)


def _week_to_domain(model: TimesheetWeekModel) -> TimesheetWeek:
    return TimesheetWeek(
        id=model.id,
        user_id=model.user_id,
        week_start_date=model.week_start_date,
        status=model.status,
        total_hours=model.total_hours,
        submitted_at=model.submitted_at,
    )


def _entry_to_domain(model: TimesheetEntryModel) -> TimesheetEntry:
    return TimesheetEntry(
        id=model.id,
        timesheet_week_id=model.timesheet_week_id,
        project_id=model.project_id,
        hours_worked=model.hours_worked,
        activity_tags=tuple(_coerce_activity_tag(tag) for tag in model.activity_tags),
    )


class SqlAlchemyTimesheetRepository:
    """Read and write timesheet weeks and entries."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def list_recent_activity_tags(
        self,
        user_id: int,
        *,
        weeks: int = 4,
        as_of: date | None = None,
    ) -> list[str]:
        reference = as_of or date.today()
        cutoff = reference - timedelta(weeks=weeks)
        weeks_models = self._session.scalars(
            select(TimesheetWeekModel)
            .where(TimesheetWeekModel.user_id == user_id)
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

    def find_week_by_user(
        self,
        user_id: int,
        week_start_date: date,
    ) -> TimesheetWeek | None:
        model = self._session.scalar(
            select(TimesheetWeekModel)
            .where(TimesheetWeekModel.user_id == user_id)
            .where(TimesheetWeekModel.week_start_date == week_start_date)
        )
        return _week_to_domain(model) if model is not None else None

    def list_entries_for_week(self, timesheet_week_id: int) -> list[TimesheetEntry]:
        models = self._session.scalars(
            select(TimesheetEntryModel)
            .where(TimesheetEntryModel.timesheet_week_id == timesheet_week_id)
            .order_by(TimesheetEntryModel.id)
        ).all()
        return [_entry_to_domain(model) for model in models]

    def list_weeks_for_user(
        self,
        user_id: int,
        *,
        limit: int | None = None,
    ) -> list[TimesheetWeek]:
        stmt = (
            select(TimesheetWeekModel)
            .where(TimesheetWeekModel.user_id == user_id)
            .order_by(TimesheetWeekModel.week_start_date.desc())
        )
        if limit is not None:
            stmt = stmt.limit(limit)
        models = self._session.scalars(stmt).all()
        return [_week_to_domain(model) for model in models]

    def create_week_with_entries(
        self,
        *,
        user_id: int,
        week_start_date: date,
        total_hours: int,
        submitted_at: datetime,
        entries: tuple[NewTimesheetEntry, ...],
    ) -> TimesheetWeek:
        week_model = TimesheetWeekModel(
            user_id=user_id,
            week_start_date=week_start_date,
            status=TimesheetWeekStatus.SUBMITTED,
            total_hours=total_hours,
            submitted_at=submitted_at,
        )
        self._session.add(week_model)
        self._session.flush()

        for entry in entries:
            self._session.add(
                TimesheetEntryModel(
                    timesheet_week_id=week_model.id,
                    project_id=entry.project_id,
                    hours_worked=entry.hours_worked,
                    activity_tags=list(entry.activity_tags),
                )
            )

        self._session.flush()
        self._session.refresh(week_model)
        return _week_to_domain(week_model)

    def create_missed_week(
        self,
        *,
        user_id: int,
        week_start_date: date,
    ) -> TimesheetWeek:
        week_model = TimesheetWeekModel(
            user_id=user_id,
            week_start_date=week_start_date,
            status=TimesheetWeekStatus.MISSED,
            total_hours=0,
            submitted_at=None,
        )
        self._session.add(week_model)
        self._session.flush()
        self._session.refresh(week_model)
        return _week_to_domain(week_model)

    def delete_missed_week(
        self,
        user_id: int,
        week_start_date: date,
    ) -> bool:
        model = self._session.scalar(
            select(TimesheetWeekModel)
            .where(TimesheetWeekModel.user_id == user_id)
            .where(TimesheetWeekModel.week_start_date == week_start_date)
            .where(TimesheetWeekModel.status == TimesheetWeekStatus.MISSED)
        )
        if model is None:
            return False
        self._session.delete(model)
        self._session.flush()
        return True
