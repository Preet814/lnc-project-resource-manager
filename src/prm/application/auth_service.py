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
    ) -> None:
        self._users = user_repository
        self._hasher = password_hasher
        self._tokens = token_service
        self._authorization = authorization or AuthorizationService()

    def login(self, username: str, password: str) -> LoginResult:
        user = self._users.find_by_username(username)
        if user is None or not self._hasher.verify(password, user.password_hash):
            raise AuthenticationError(_INVALID_CREDENTIALS_MESSAGE)

        self._authorization.assert_active(user)

        auth_token = self._tokens.create_access_token(
            user_id=user.id,
            username=user.username,
            role=user.role,
            force_password_change=user.force_password_change,
        )
        return LoginResult(
            access_token=auth_token.token,
            token_type="bearer",
            user_id=user.id,
            username=user.username,
            full_name=user.full_name,
            role=user.role,
            force_password_change=user.force_password_change,
            expires_at=auth_token.expires_at,
        )

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

        auth_token = self._tokens.create_access_token(
            user_id=updated.id,
            username=updated.username,
            role=updated.role,
            force_password_change=False,
        )
        login_result = LoginResult(
            access_token=auth_token.token,
            token_type="bearer",
            user_id=updated.id,
            username=updated.username,
            full_name=updated.full_name,
            role=updated.role,
            force_password_change=False,
            expires_at=auth_token.expires_at,
        )
        return updated, login_result
