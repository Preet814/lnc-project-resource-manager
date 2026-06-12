"""User persistence via SQLAlchemy."""

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from prm.domain.entities.user import User
from prm.domain.enums import ResourceWorkStatus, Role, UserAccountStatus
from prm.domain.exceptions import NotFoundError
from prm.infrastructure.db.models import (
    DepartmentModel,
    DesignationModel,
    ResourceStatusModel,
    RoleModel,
    UserModel,
)


def _role_from_code(code: str) -> Role:
    return Role(code)


def _to_domain(model: UserModel) -> User:
    role_code = model.role.code if model.role is not None else Role.ENGINEER
    resource = model.resource_status
    return User(
        id=model.id,
        full_name=model.full_name,
        username=model.username,
        email=model.email,
        password_hash=model.password_hash,
        role_id=model.role_id,
        role=_role_from_code(role_code),
        department_id=model.department_id,
        designation_id=model.designation_id,
        manager_id=model.manager_id,
        account_status=model.account_status,
        force_password_change=model.force_password_change,
        created_at=model.created_at,
        updated_at=model.updated_at,
        department_name=model.department.name if model.department is not None else None,
        designation_name=model.designation.name if model.designation is not None else None,
        work_status=resource.work_status if resource is not None else None,
        utilisation_percent=resource.utilisation_percent if resource is not None else None,
    )


def _user_query():
    return select(UserModel).options(
        joinedload(UserModel.role),
        joinedload(UserModel.department),
        joinedload(UserModel.designation),
        joinedload(UserModel.resource_status),
    )


class SqlAlchemyUserRepository:
    """Load and update users from the users table."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def find_by_username(self, username: str) -> User | None:
        model = self._session.scalar(
            _user_query().where(UserModel.username == username)
        )
        return _to_domain(model) if model is not None else None

    def find_by_id(self, user_id: int) -> User | None:
        model = self._session.scalar(_user_query().where(UserModel.id == user_id))
        return _to_domain(model) if model is not None else None

    def find_by_email(self, email: str) -> User | None:
        model = self._session.scalar(_user_query().where(UserModel.email == email))
        return _to_domain(model) if model is not None else None

    def list_all(self) -> list[User]:
        models = self._session.scalars(_user_query().order_by(UserModel.id)).all()
        return [_to_domain(model) for model in models]

    def list_engineers(
        self,
        *,
        work_status: ResourceWorkStatus | None = None,
        department_id: int | None = None,
        active_only: bool = True,
    ) -> list[User]:
        engineer_role_id = self._engineer_role_id()
        stmt = _user_query().where(UserModel.role_id == engineer_role_id)
        if active_only:
            stmt = stmt.where(UserModel.account_status == UserAccountStatus.ACTIVE)
        if department_id is not None:
            stmt = stmt.where(UserModel.department_id == department_id)
        if work_status is not None:
            stmt = stmt.join(ResourceStatusModel).where(
                ResourceStatusModel.work_status == work_status
            )
        models = self._session.scalars(stmt.order_by(UserModel.id)).all()
        return [_to_domain(model) for model in models]

    def list_by_manager_id(
        self,
        manager_id: int,
        *,
        active_only: bool = True,
        engineers_only: bool = True,
    ) -> list[User]:
        stmt = _user_query().where(UserModel.manager_id == manager_id)
        if active_only:
            stmt = stmt.where(UserModel.account_status == UserAccountStatus.ACTIVE)
        if engineers_only:
            stmt = stmt.where(UserModel.role_id == self._engineer_role_id())
        models = self._session.scalars(stmt.order_by(UserModel.id)).all()
        return [_to_domain(model) for model in models]

    def create(
        self,
        *,
        full_name: str,
        username: str,
        email: str,
        password_hash: str,
        role_id: int,
        department_id: int | None = None,
        designation_id: int | None = None,
        manager_id: int | None = None,
        force_password_change: bool = True,
        account_status: UserAccountStatus = UserAccountStatus.ACTIVE,
    ) -> User:
        model = UserModel(
            full_name=full_name,
            username=username,
            email=email,
            password_hash=password_hash,
            role_id=role_id,
            department_id=department_id,
            designation_id=designation_id,
            manager_id=manager_id,
            account_status=account_status,
            force_password_change=force_password_change,
        )
        self._session.add(model)
        self._session.flush()
        role = self._session.get(RoleModel, role_id)
        if role is not None and role.hierarchy_rank == 1:
            self._session.add(
                ResourceStatusModel(
                    user_id=model.id,
                    work_status=ResourceWorkStatus.BENCH,
                    utilisation_percent=0,
                )
            )
            self._session.flush()
        return self._require_domain(model.id)

    def update_profile(
        self,
        user_id: int,
        *,
        full_name: str | None = None,
        email: str | None = None,
        department_id: int | None = None,
        designation_id: int | None = None,
        manager_id: int | None = None,
    ) -> User:
        model = self._session.get(UserModel, user_id)
        if model is None:
            raise NotFoundError(f"User {user_id} not found.")
        if full_name is not None:
            model.full_name = full_name
        if email is not None:
            model.email = email
        if department_id is not None:
            model.department_id = department_id
        if designation_id is not None:
            model.designation_id = designation_id
        if manager_id is not None:
            model.manager_id = manager_id
        self._session.flush()
        return self._require_domain(user_id)

    def set_manager_id(self, user_id: int, *, manager_id: int | None) -> User:
        model = self._session.get(UserModel, user_id)
        if model is None:
            raise NotFoundError(f"User {user_id} not found.")
        model.manager_id = manager_id
        self._session.flush()
        return self._require_domain(user_id)

    def update_password(
        self,
        user_id: int,
        *,
        password_hash: str,
        force_password_change: bool,
    ) -> User:
        model = self._session.get(UserModel, user_id)
        if model is None:
            raise NotFoundError(f"User {user_id} not found.")
        model.password_hash = password_hash
        model.force_password_change = force_password_change
        self._session.flush()
        return self._require_domain(user_id)

    def update_account_status(
        self,
        user_id: int,
        *,
        account_status: UserAccountStatus,
    ) -> User:
        model = self._session.get(UserModel, user_id)
        if model is None:
            raise NotFoundError(f"User {user_id} not found.")
        model.account_status = account_status
        self._session.flush()
        return self._require_domain(user_id)

    def update_role(self, user_id: int, *, role_id: int) -> User:
        model = self._session.get(UserModel, user_id)
        if model is None:
            raise NotFoundError(f"User {user_id} not found.")
        model.role_id = role_id
        role = self._session.get(RoleModel, role_id)
        resource = self._session.get(ResourceStatusModel, user_id)
        if role is not None and role.hierarchy_rank == 1 and resource is None:
            self._session.add(
                ResourceStatusModel(
                    user_id=user_id,
                    work_status=ResourceWorkStatus.BENCH,
                    utilisation_percent=0,
                )
            )
        elif role is not None and role.hierarchy_rank != 1 and resource is not None:
            self._session.delete(resource)
        self._session.flush()
        return self._require_domain(user_id)

    def update_resource_status(
        self,
        user_id: int,
        *,
        utilisation_percent: int,
        work_status: ResourceWorkStatus,
    ) -> User:
        resource = self._session.get(ResourceStatusModel, user_id)
        if resource is None:
            raise NotFoundError(f"Resource status for user {user_id} not found.")
        resource.utilisation_percent = utilisation_percent
        resource.work_status = work_status
        self._session.flush()
        return self._require_domain(user_id)

    def resolve_role_id(self, role: Role) -> int:
        if role == Role.ENGINEER:
            return self._engineer_role_id()
        return self._role_id_for_code(role.value)

    def resolve_department_id(self, name: str) -> int | None:
        model = self._session.scalar(
            select(DepartmentModel).where(DepartmentModel.name == name)
        )
        return model.id if model is not None else None

    def resolve_designation_id(self, name: str) -> int | None:
        model = self._session.scalar(
            select(DesignationModel).where(DesignationModel.name == name)
        )
        return model.id if model is not None else None

    def _role_id_for_code(self, code: str) -> int:
        role_id = self._session.scalar(
            select(RoleModel.id).where(RoleModel.code == code)
        )
        if role_id is None:
            raise RuntimeError(f"Role '{code}' not seeded.")
        return role_id

    def _engineer_role_id(self) -> int:
        return self._role_id_for_code(Role.ENGINEER.value)

    def _require_domain(self, user_id: int) -> User:
        user = self.find_by_id(user_id)
        if user is None:
            raise NotFoundError(f"User {user_id} not found.")
        return user
