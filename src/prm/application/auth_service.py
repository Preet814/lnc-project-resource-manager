"""Authentication use cases — login and forced password change."""

from prm.application.authorization_service import AuthorizationService
from prm.application.protocols import PasswordHasher, TokenService, UserRepository
from prm.domain.dtos import LoginResult
from prm.domain.entities.user import User
from prm.domain.exceptions import AuthenticationError, ValidationError
from prm.domain.password_policy import validate_password_strength

_INVALID_CREDENTIALS_MESSAGE = "Invalid username or password."


class AuthService:
    """Validate credentials, issue tokens, and complete password changes."""

    def __init__(
        self,
        user_repository: UserRepository,
        password_hasher: PasswordHasher,
        token_service: TokenService,
        authorization: AuthorizationService | None = None,
        *,
        email_verification_required: bool = True,
    ) -> None:
        self._users = user_repository
        self._hasher = password_hasher
        self._tokens = token_service
        self._authorization = authorization or AuthorizationService()
        self._email_verification_required = email_verification_required

    def login(self, username: str, password: str) -> LoginResult:
        user = self._users.find_by_username(username)
        if user is None or not self._hasher.verify(password, user.password_hash):
            raise AuthenticationError(_INVALID_CREDENTIALS_MESSAGE)

        self._authorization.assert_active(user)
        return self._login_result_for_user(user)

    def change_password(
        self,
        user_id: int,
        *,
        new_password: str,
        confirm_password: str,
    ) -> tuple[User, LoginResult]:
        if new_password != confirm_password:
            raise ValidationError("New password and confirmation do not match.")

        validate_password_strength(new_password)

        user = self._users.find_by_id(user_id)
        if user is None:
            raise AuthenticationError(_INVALID_CREDENTIALS_MESSAGE)

        self._authorization.assert_active(user)

        updated = self._users.update_password(
            user_id,
            password_hash=self._hasher.hash(new_password),
            force_password_change=False,
        )
        return updated, self._login_result_for_user(updated)

    def _login_result_for_user(self, user: User) -> LoginResult:
        email_verified = self._effective_email_verified(user)
        auth_token = self._tokens.create_access_token(
            user_id=user.id,
            username=user.username,
            role=user.role,
            force_password_change=user.force_password_change,
            email_verified=email_verified,
        )
        return LoginResult(
            access_token=auth_token.token,
            token_type="bearer",
            user_id=user.id,
            username=user.username,
            full_name=user.full_name,
            role=user.role,
            force_password_change=user.force_password_change,
            email_verified=email_verified,
            expires_at=auth_token.expires_at,
        )

    def _effective_email_verified(self, user: User) -> bool:
        if not self._email_verification_required:
            return True
        return user.email_verified
