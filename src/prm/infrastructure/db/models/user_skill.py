"""User skill assignment ORM models."""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from prm.domain.enums import ProficiencyLevel, SkillCategory
from prm.infrastructure.db.base import Base
from prm.infrastructure.db.models._types import proficiency_level_enum, skill_category_enum


class SkillModel(Base):
    """Reusable skill catalog entry."""

    __tablename__ = "skills"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(unique=True, nullable=False)
    category: Mapped[SkillCategory] = mapped_column(skill_category_enum, nullable=False)
    is_predefined: Mapped[bool] = mapped_column(nullable=False, default=False)

    user_skills = relationship("UserSkillModel", back_populates="skill")


class UserSkillModel(Base):
    """Links users to skills with proficiency."""

    __tablename__ = "user_skills"
    __table_args__ = (UniqueConstraint("user_id", "skill_id", name="uq_user_skill"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    skill_id: Mapped[int] = mapped_column(
        ForeignKey("skills.id", ondelete="CASCADE"), nullable=False, index=True
    )
    proficiency: Mapped[ProficiencyLevel] = mapped_column(
        proficiency_level_enum, nullable=False
    )
    assigned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    user = relationship("UserModel", back_populates="user_skills")
    skill = relationship("SkillModel", back_populates="user_skills")
