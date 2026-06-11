"""Permission and role-permission ORM models."""

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from prm.infrastructure.db.base import Base


class PermissionModel(Base):
    """Atomic permission for RBAC."""

    __tablename__ = "permissions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    hierarchy_level: Mapped[int] = mapped_column(Integer, nullable=False)
    module: Mapped[str] = mapped_column(String(50), nullable=False)

    role_permissions = relationship("RolePermissionModel", back_populates="permission")


class RolePermissionModel(Base):
    """Many-to-many role ↔ permission."""

    __tablename__ = "role_permissions"

    role_id: Mapped[int] = mapped_column(
        ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True
    )
    permission_id: Mapped[int] = mapped_column(
        ForeignKey("permissions.id", ondelete="CASCADE"), primary_key=True
    )

    role = relationship("RoleModel", back_populates="role_permissions")
    permission = relationship("PermissionModel", back_populates="role_permissions")
