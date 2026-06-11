"""Designation ORM model."""

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from prm.infrastructure.db.base import Base


class DesignationModel(Base):
    """Job title / designation."""

    __tablename__ = "designations"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    track: Mapped[str | None] = mapped_column(String(50), nullable=True)

    users = relationship("UserModel", back_populates="designation")
