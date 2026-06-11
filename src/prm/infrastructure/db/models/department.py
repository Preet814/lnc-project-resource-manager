"""Department ORM model."""

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from prm.infrastructure.db.base import Base


class DepartmentModel(Base):
    """Organisational department."""

    __tablename__ = "departments"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)

    users = relationship("UserModel", back_populates="department")
