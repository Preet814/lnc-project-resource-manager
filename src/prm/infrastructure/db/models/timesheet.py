"""Timesheet ORM models."""

from datetime import date, datetime

from sqlalchemy import ARRAY, Date, DateTime, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from prm.domain.enums import ActivityTag, TimesheetWeekStatus
from prm.infrastructure.db.base import Base
from prm.infrastructure.db.models._types import activity_tag_enum, timesheet_week_status_enum


class TimesheetWeekModel(Base):
    """Weekly timesheet aggregate for an employee."""

    __tablename__ = "timesheet_weeks"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    employee_id: Mapped[int] = mapped_column(
        ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, index=True
    )
    week_start_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[TimesheetWeekStatus] = mapped_column(
        timesheet_week_status_enum, nullable=False, default=TimesheetWeekStatus.SUBMITTED
    )
    total_hours: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    employee = relationship("EmployeeModel", back_populates="timesheet_weeks")
    entries = relationship(
        "TimesheetEntryModel", back_populates="timesheet_week", cascade="all, delete-orphan"
    )


class TimesheetEntryModel(Base):
    """Daily/project line within a timesheet week."""

    __tablename__ = "timesheet_entries"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    timesheet_week_id: Mapped[int] = mapped_column(
        ForeignKey("timesheet_weeks.id", ondelete="CASCADE"), nullable=False, index=True
    )
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    hours_worked: Mapped[int] = mapped_column(Integer, nullable=False)
    activity_tags: Mapped[list[ActivityTag]] = mapped_column(
        ARRAY(activity_tag_enum), nullable=False, insert_default=list
    )

    timesheet_week = relationship("TimesheetWeekModel", back_populates="entries")
    project = relationship("ProjectModel", back_populates="timesheet_entries")
