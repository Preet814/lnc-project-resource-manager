"""Application-layer protocols (dependency inversion)."""

from datetime import datetime
from typing import Protocol

from prm.domain.dtos import AuthToken
from prm.domain.entities.user import User
from prm.domain.enums import Role, UserAccountStatus


class PasswordHasher(Protocol):
    def hash(self, password: str) -> str: ...

    def verify(self, password: str, password_hash: str) -> bool: ...


class TokenPayload(Protocol):
    user_id: int
    username: str
    role: Role
    force_password_change: bool
    expires_at: datetime


class TokenService(Protocol):
    def create_access_token(
        self,
        *,
        user_id: int,
        username: str,
        role: Role,
        force_password_change: bool,
    ) -> AuthToken: ...

    def decode_access_token(self, token: str) -> TokenPayload: ...


class UserRepository(Protocol):
    def find_by_username(self, username: str) -> User | None: ...

    def find_by_id(self, user_id: int) -> User | None: ...

    def find_by_email(self, email: str) -> User | None: ...

    def list_all(self) -> list[User]: ...

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
    ) -> User: ...

    def update_password(
        self,
        user_id: int,
        *,
        password_hash: str,
        force_password_change: bool,
    ) -> User: ...

    def update_account_status(
        self,
        user_id: int,
        *,
        account_status: UserAccountStatus,
    ) -> User: ...
