"""Employee and skill ORM models."""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from prm.domain.enums import EmployeeWorkStatus, ProficiencyLevel, SkillCategory
from prm.infrastructure.db.base import Base
from prm.infrastructure.db.models._types import (
    employee_work_status_enum,
    proficiency_level_enum,
    skill_category_enum,
)


class EmployeeModel(Base):
    """Employee work profile linked optionally to a user account."""

    __tablename__ = "employees"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), unique=True, nullable=True
    )
    manager_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    department: Mapped[str] = mapped_column(String(255), nullable=False)
    designation: Mapped[str] = mapped_column(String(255), nullable=False)
    work_status: Mapped[EmployeeWorkStatus] = mapped_column(
        employee_work_status_enum, nullable=False, default=EmployeeWorkStatus.BENCH
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    current_utilisation_percent: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    user = relationship("UserModel", back_populates="employee")
    skills = relationship("EmployeeSkillModel", back_populates="employee")
    allocations = relationship("AllocationModel", back_populates="employee")
    timesheet_weeks = relationship("TimesheetWeekModel", back_populates="employee")


class SkillModel(Base):
    """Reusable skill catalog entry."""

    __tablename__ = "skills"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    category: Mapped[SkillCategory] = mapped_column(skill_category_enum, nullable=False)
    is_predefined: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    employee_skills = relationship("EmployeeSkillModel", back_populates="skill")


class EmployeeSkillModel(Base):
    """Assignment of a skill to an employee with proficiency."""

    __tablename__ = "employee_skills"
    __table_args__ = (UniqueConstraint("employee_id", "skill_id", name="uq_employee_skill"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    employee_id: Mapped[int] = mapped_column(
        ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, index=True
    )
    skill_id: Mapped[int] = mapped_column(
        ForeignKey("skills.id", ondelete="CASCADE"), nullable=False, index=True
    )
    proficiency: Mapped[ProficiencyLevel] = mapped_column(proficiency_level_enum, nullable=False)
    assigned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    employee = relationship("EmployeeModel", back_populates="skills")
    skill = relationship("SkillModel", back_populates="employee_skills")
