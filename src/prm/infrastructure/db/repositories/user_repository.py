"""User persistence via SQLAlchemy."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from prm.domain.entities.user import User
from prm.domain.enums import Role, UserAccountStatus
from prm.domain.exceptions import NotFoundError
from prm.infrastructure.db.models import UserModel


def _to_domain(model: UserModel) -> User:
    return User(
        id=model.id,
        full_name=model.full_name,
        username=model.username,
        email=model.email,
        password_hash=model.password_hash,
        role=model.role,
        account_status=model.account_status,
        force_password_change=model.force_password_change,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


class SqlAlchemyUserRepository:
    """Load and update users from the users table."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def find_by_username(self, username: str) -> User | None:
        model = self._session.scalar(
            select(UserModel).where(UserModel.username == username)
        )
        return _to_domain(model) if model is not None else None

    def find_by_id(self, user_id: int) -> User | None:
        model = self._session.get(UserModel, user_id)
        return _to_domain(model) if model is not None else None

    def find_by_email(self, email: str) -> User | None:
        model = self._session.scalar(
            select(UserModel).where(UserModel.email == email)
        )
        return _to_domain(model) if model is not None else None

    def list_all(self) -> list[User]:
        models = self._session.scalars(
            select(UserModel).order_by(UserModel.id)
        ).all()
        return [_to_domain(model) for model in models]

    def create(
        self,
        *,
        full_name: str,
        username: str,
        email: str,
        password_hash: str,
        role: Role,
        force_password_change: bool = True,
        account_status: UserAccountStatus = UserAccountStatus.ACTIVE,
    ) -> User:
        model = UserModel(
            full_name=full_name,
            username=username,
            email=email,
            password_hash=password_hash,
            role=role,
            account_status=account_status,
            force_password_change=force_password_change,
        )
        self._session.add(model)
        self._session.flush()
        self._session.refresh(model)
        return _to_domain(model)

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
        self._session.refresh(model)
        return _to_domain(model)

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
        self._session.refresh(model)
        return _to_domain(model)
