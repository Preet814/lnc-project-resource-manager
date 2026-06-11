"""Role ORM model."""

from sqlalchemy import Boolean, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from prm.infrastructure.db.base import Base


class RoleModel(Base):
    """RBAC role with hierarchy rank."""

    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    hierarchy_rank: Mapped[int] = mapped_column(Integer, nullable=False)
    is_system: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    users = relationship("UserModel", back_populates="role")
    role_permissions = relationship("RolePermissionModel", back_populates="role")
