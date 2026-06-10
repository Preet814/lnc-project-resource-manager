"""User ORM model."""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from prm.domain.enums import Role, UserAccountStatus
from prm.infrastructure.db.base import Base
from prm.infrastructure.db.models._types import role_enum, user_account_status_enum


class UserModel(Base):
    """Persisted user account (Admin, Manager, or Employee login)."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    username: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[Role] = mapped_column(role_enum, nullable=False)
    account_status: Mapped[UserAccountStatus] = mapped_column(
        user_account_status_enum, nullable=False, default=UserAccountStatus.ACTIVE
    )
    force_password_change: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    employee = relationship(
        "EmployeeModel",
        back_populates="user",
        foreign_keys="EmployeeModel.user_id",
        uselist=False,
    )
    team_members = relationship(
        "EmployeeModel",
        back_populates="manager",
        foreign_keys="EmployeeModel.manager_id",
    )
    managed_projects = relationship("ProjectModel", back_populates="manager")
    created_allocations = relationship("AllocationModel", back_populates="created_by")
