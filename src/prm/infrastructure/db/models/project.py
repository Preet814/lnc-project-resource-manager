"""Project, milestone, and health snapshot ORM models."""

from datetime import date, datetime

from sqlalchemy import ARRAY, Date, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from prm.domain.enums import MilestoneStatus, ProjectHealthStatus, ProjectStatus
from prm.infrastructure.db.base import Base
from prm.infrastructure.db.models._types import (
    milestone_status_enum,
    project_health_status_enum,
    project_status_enum,
)


class ProjectModel(Base):
    """Project master record."""

    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[ProjectStatus] = mapped_column(
        project_status_enum, nullable=False, default=ProjectStatus.PLANNED
    )
    manager_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    total_story_points: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    health_status: Mapped[ProjectHealthStatus] = mapped_column(
        project_health_status_enum, nullable=False, default=ProjectHealthStatus.ON_TRACK
    )
    health_computed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    manager = relationship("UserModel", back_populates="managed_projects")
    milestones = relationship(
        "MilestoneModel", back_populates="project", cascade="all, delete-orphan"
    )
    allocations = relationship("AllocationModel", back_populates="project")
    timesheet_entries = relationship("TimesheetEntryModel", back_populates="project")
    health_snapshots = relationship(
        "ProjectHealthSnapshotModel", back_populates="project", cascade="all, delete-orphan"
    )


class MilestoneModel(Base):
    """Project milestone."""

    __tablename__ = "milestones"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    due_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[MilestoneStatus] = mapped_column(
        milestone_status_enum, nullable=False, default=MilestoneStatus.NOT_STARTED
    )
    sequence_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    story_points: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    project = relationship("ProjectModel", back_populates="milestones")


class ProjectHealthSnapshotModel(Base):
    """Point-in-time project health snapshot with risk flags."""

    __tablename__ = "project_health_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[ProjectHealthStatus] = mapped_column(project_health_status_enum, nullable=False)
    risk_flags: Mapped[list[str]] = mapped_column(
        ARRAY(String(255)), nullable=False, insert_default=list
    )
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    project = relationship("ProjectModel", back_populates="health_snapshots")
