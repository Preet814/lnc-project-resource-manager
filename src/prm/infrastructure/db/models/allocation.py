"""Allocation ORM model."""

from datetime import date

from sqlalchemy import Date, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from prm.domain.enums import AllocationStatus
from prm.infrastructure.db.base import Base
from prm.infrastructure.db.models._types import allocation_status_enum


class AllocationModel(Base):
    """Engineer allocation to a project for a date range."""

    __tablename__ = "allocations"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    utilisation_percent: Mapped[int] = mapped_column(Integer, nullable=False)
    from_date: Mapped[date] = mapped_column(Date, nullable=False)
    to_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[AllocationStatus] = mapped_column(
        allocation_status_enum, nullable=False, default=AllocationStatus.ACTIVE
    )
    created_by_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )

    user = relationship(
        "UserModel",
        back_populates="allocations",
        foreign_keys=[user_id],
    )
    project = relationship("ProjectModel", back_populates="allocations")
    created_by = relationship(
        "UserModel",
        back_populates="created_allocations",
        foreign_keys=[created_by_user_id],
    )
