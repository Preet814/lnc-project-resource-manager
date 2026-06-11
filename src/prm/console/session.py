"""Authenticated console session state."""

from dataclasses import dataclass

from prm.domain.enums import Role


@dataclass
class UserSession:
    access_token: str
    user_id: int
    username: str
    full_name: str
    role: Role
    force_password_change: bool

    @classmethod
    def empty(cls) -> "UserSession":
        return cls(
            access_token="",
            user_id=0,
            username="",
            full_name="",
            role=Role.ADMIN,
            force_password_change=False,
        )

    @property
    def is_authenticated(self) -> bool:
        return bool(self.access_token)

    def apply_login(
        self,
        *,
        access_token: str,
        user_id: int,
        username: str,
        full_name: str,
        role: Role,
        force_password_change: bool,
    ) -> None:
        self.access_token = access_token
        self.user_id = user_id
        self.username = username
        self.full_name = full_name
        self.role = role
        self.force_password_change = force_password_change

    def clear(self) -> None:
        empty = self.empty()
        self.access_token = empty.access_token
        self.user_id = empty.user_id
        self.username = empty.username
        self.full_name = empty.full_name
        self.role = empty.role
        self.force_password_change = empty.force_password_change
