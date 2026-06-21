"""User ORM model."""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from prm.domain.enums import UserAccountStatus
from prm.infrastructure.db.base import Base
from prm.infrastructure.db.models._types import user_account_status_enum


class UserModel(Base):
    """Persisted person account — admin, manager, or engineer."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    username: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role_id: Mapped[int] = mapped_column(ForeignKey("roles.id"), nullable=False, index=True)
    department_id: Mapped[int | None] = mapped_column(
        ForeignKey("departments.id"), nullable=True, index=True
    )
    designation_id: Mapped[int | None] = mapped_column(
        ForeignKey("designations.id"), nullable=True, index=True
    )
    manager_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    account_status: Mapped[UserAccountStatus] = mapped_column(
        user_account_status_enum, nullable=False, default=UserAccountStatus.ACTIVE
    )
    force_password_change: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    email_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    role = relationship("RoleModel", back_populates="users")
    department = relationship("DepartmentModel", back_populates="users")
    designation = relationship("DesignationModel", back_populates="users")
    manager = relationship(
        "UserModel",
        remote_side="UserModel.id",
        foreign_keys=[manager_id],
        back_populates="direct_reports",
    )
    direct_reports = relationship(
        "UserModel",
        back_populates="manager",
        foreign_keys=[manager_id],
    )
    resource_status = relationship(
        "ResourceStatusModel",
        back_populates="user",
        uselist=False,
    )
    user_skills = relationship("UserSkillModel", back_populates="user")
    managed_projects = relationship("ProjectModel", back_populates="manager")
    created_allocations = relationship(
        "AllocationModel",
        back_populates="created_by",
        foreign_keys="AllocationModel.created_by_user_id",
    )
    allocations = relationship(
        "AllocationModel",
        back_populates="user",
        foreign_keys="AllocationModel.user_id",
    )
    timesheet_weeks = relationship("TimesheetWeekModel", back_populates="user")
