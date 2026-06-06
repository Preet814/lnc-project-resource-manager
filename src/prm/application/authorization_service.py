"""Role and account-status checks (DRY for future protected endpoints)."""

from prm.domain.entities.user import User
from prm.domain.enums import Role
from prm.domain.exceptions import UnauthorizedError


class AuthorizationService:
    """Centralize who may perform an action."""

    def assert_active(self, user: User) -> None:
        if not user.is_active():
            raise UnauthorizedError("Account is inactive.")

    def assert_role(self, user: User, *allowed_roles: Role) -> None:
        if user.role not in allowed_roles:
            raise UnauthorizedError(
                f"Role {user.role.value} is not permitted for this action."
            )
