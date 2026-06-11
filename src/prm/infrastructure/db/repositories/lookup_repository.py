"""Read-only lookup repositories for roles, departments, and designations."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from prm.infrastructure.db.models import DepartmentModel, DesignationModel, RoleModel


class SqlAlchemyLookupRepository:
    """List RBAC and org lookup values."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def list_roles(self) -> list[tuple[int, str, str, int]]:
        rows = self._session.scalars(select(RoleModel).order_by(RoleModel.id)).all()
        return [(row.id, row.code, row.name, row.hierarchy_rank) for row in rows]

    def list_departments(self) -> list[tuple[int, str]]:
        rows = self._session.scalars(select(DepartmentModel).order_by(DepartmentModel.name)).all()
        return [(row.id, row.name) for row in rows]

    def list_designations(self) -> list[tuple[int, str, str | None]]:
        rows = self._session.scalars(
            select(DesignationModel).order_by(DesignationModel.name)
        ).all()
        return [(row.id, row.name, row.track) for row in rows]

    def find_role_by_code(self, code: str) -> tuple[int, int] | None:
        row = self._session.scalar(select(RoleModel).where(RoleModel.code == code))
        if row is None:
            return None
        return row.id, row.hierarchy_rank
