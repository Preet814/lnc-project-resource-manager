"""Admin user-management use cases (BRD §3.4)."""

from prm.application.protocols import PasswordHasher, UserRepository
from prm.domain.dtos import UserListResult, UserSummary
from prm.domain.entities.user import User
from prm.domain.enums import Role, UserAccountStatus
from prm.domain.exceptions import NotFoundError, ValidationError
from prm.domain.password_policy import validate_password_strength


class UserManagementService:
    """Create, list, reactivate, deactivate, and reset passwords for user accounts."""

    def __init__(
        self,
        user_repository: UserRepository,
        password_hasher: PasswordHasher,
    ) -> None:
        self._users = user_repository
        self._hasher = password_hasher

    def create_user(
        self,
        *,
        full_name: str,
        email: str,
        username: str,
        temporary_password: str,
        role: Role,
    ) -> User:
        validate_password_strength(temporary_password)

        if self._users.find_by_username(username) is not None:
            raise ValidationError(f"Username '{username}' is already in use.")
        if self._users.find_by_email(email) is not None:
            raise ValidationError(f"Email '{email}' is already in use.")

        department_name = "IT" if role == Role.ADMIN else "Engineering"
        designation_by_role = {
            Role.ADMIN: "System Administrator",
            Role.MANAGER: "Project Manager",
            Role.ENGINEER: "SE",
        }
        department_id = self._users.resolve_department_id(department_name)
        designation_id = self._users.resolve_designation_id(designation_by_role[role])
        if department_id is None or designation_id is None:
            raise ValidationError("Default department or designation is not configured.")

        return self._users.create(
            full_name=full_name,
            username=username,
            email=email,
            password_hash=self._hasher.hash(temporary_password),
            role_id=self._users.resolve_role_id(role),
            department_id=department_id,
            designation_id=designation_id,
            force_password_change=True,
            account_status=UserAccountStatus.ACTIVE,
        )

    def list_users(self) -> UserListResult:
        users = self._users.list_all()
        summaries = tuple(
            UserSummary(
                id=user.id,
                username=user.username,
                full_name=user.full_name,
                role=user.role,
                account_status=user.account_status,
            )
            for user in users
        )
        active_count = sum(1 for summary in summaries if summary.is_active())
        inactive_count = len(summaries) - active_count
        return UserListResult(
            users=summaries,
            total=len(summaries),
            active_count=active_count,
            inactive_count=inactive_count,
        )

    def reactivate_user(self, user_id: int) -> User:
        user = self._require_user_by_id(user_id)
        if user.is_active():
            raise ValidationError(f"User '{user.username}' is already active.")
        return self._users.update_account_status(
            user_id,
            account_status=UserAccountStatus.ACTIVE,
        )

    def deactivate_user(self, user_id: int, *, actor_user_id: int) -> User:
        if user_id == actor_user_id:
            raise ValidationError("You cannot deactivate your own account.")

        user = self._require_user_by_id(user_id)
        if not user.is_active():
            raise ValidationError(f"User '{user.username}' is already inactive.")
        return self._users.update_account_status(
            user_id,
            account_status=UserAccountStatus.INACTIVE,
        )

    def reset_password(self, identifier: str, *, temporary_password: str) -> User:
        validate_password_strength(temporary_password)
        user = self._resolve_user(identifier)
        return self._users.update_password(
            user.id,
            password_hash=self._hasher.hash(temporary_password),
            force_password_change=True,
        )

    def _require_user_by_id(self, user_id: int) -> User:
        user = self._users.find_by_id(user_id)
        if user is None:
            raise NotFoundError(f"User {user_id} not found.")
        return user

    def _resolve_user(self, identifier: str) -> User:
        stripped = identifier.strip()
        if not stripped:
            raise ValidationError("User identifier is required.")

        if stripped.isdigit():
            user = self._users.find_by_id(int(stripped))
        else:
            user = self._users.find_by_username(stripped)

        if user is None:
            raise NotFoundError(f"User '{stripped}' not found.")
        return user
