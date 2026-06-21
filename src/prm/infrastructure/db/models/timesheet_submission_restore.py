"""Persisted manager restores for frozen timesheet submission weeks."""

from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from prm.infrastructure.db.base import Base


class TimesheetSubmissionRestoreModel(Base):
    __tablename__ = "timesheet_submission_restores"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "week_start_date",
            name="uq_timesheet_submission_restores_user_week",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    week_start_date: Mapped[date] = mapped_column(Date, nullable=False)
    restored_by_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
    )
    restored_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    user = relationship("UserModel", foreign_keys=[user_id])
    restored_by = relationship("UserModel", foreign_keys=[restored_by_user_id])
