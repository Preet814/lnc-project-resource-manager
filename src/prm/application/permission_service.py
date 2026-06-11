"""Permission checks via role_permissions."""

from prm.application.protocols import PermissionRepository, UserRepository
from prm.domain.exceptions import UnauthorizedError


class PermissionService:
    """Resolve and assert permissions for a user."""

    def __init__(
        self,
        user_repository: UserRepository,
        permission_repository: PermissionRepository,
    ) -> None:
        self._users = user_repository
        self._permissions = permission_repository

    def permission_codes_for_user(self, user_id: int) -> frozenset[str]:
        user = self._users.find_by_id(user_id)
        if user is None:
            return frozenset()
        return self._permissions.list_codes_for_role(user.role_id)

    def has_permission(self, user_id: int, permission_code: str) -> bool:
        return permission_code in self.permission_codes_for_user(user_id)

    def assert_permission(self, user_id: int, permission_code: str) -> None:
        if not self.has_permission(user_id, permission_code):
            raise UnauthorizedError(
                f"Permission '{permission_code}' is required for this action."
            )
