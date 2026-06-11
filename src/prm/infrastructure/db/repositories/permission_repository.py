"""Permission persistence via SQLAlchemy."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from prm.infrastructure.db.models import PermissionModel, RolePermissionModel


class SqlAlchemyPermissionRepository:
    """Load permission codes granted to a role."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def list_codes_for_role(self, role_id: int) -> frozenset[str]:
        rows = self._session.scalars(
            select(PermissionModel.code)
            .join(RolePermissionModel, RolePermissionModel.permission_id == PermissionModel.id)
            .where(RolePermissionModel.role_id == role_id)
        ).all()
        return frozenset(rows)
