"""JWT access token creation and validation."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from jose import JWTError, jwt

from prm.domain.dtos import AuthToken
from prm.domain.enums import Role
from prm.domain.exceptions import AuthenticationError

JWT_ALGORITHM = "HS256"


@dataclass(frozen=True, slots=True)
class JwtTokenPayload:
    """Decoded JWT claims exposed to application services."""

    user_id: int
    username: str
    role: Role
    force_password_change: bool
    expires_at: datetime


class JwtTokenService:
    """Create and decode HS256 JWT access tokens."""

    def __init__(self, *, secret_key: str, expire_minutes: int) -> None:
        self._secret_key = secret_key
        self._expire_minutes = expire_minutes

    def create_access_token(
        self,
        *,
        user_id: int,
        username: str,
        role: Role,
        force_password_change: bool,
    ) -> AuthToken:
        expires_at = datetime.now(UTC) + timedelta(minutes=self._expire_minutes)
        claims = {
            "sub": str(user_id),
            "username": username,
            "role": role.value,
            "force_password_change": force_password_change,
            "exp": expires_at,
        }
        encoded = jwt.encode(claims, self._secret_key, algorithm=JWT_ALGORITHM)
        return AuthToken(token=encoded, user_id=user_id, expires_at=expires_at)

    def decode_access_token(self, token: str) -> JwtTokenPayload:
        try:
            claims = jwt.decode(token, self._secret_key, algorithms=[JWT_ALGORITHM])
        except JWTError as exc:
            raise AuthenticationError("Invalid or expired access token.") from exc

        try:
            user_id = int(claims["sub"])
            username = str(claims["username"])
            role = Role(str(claims["role"]))
            force_password_change = bool(claims["force_password_change"])
            exp = claims["exp"]
            expires_at = datetime.fromtimestamp(exp, tz=UTC)
        except (KeyError, TypeError, ValueError) as exc:
            raise AuthenticationError("Invalid access token payload.") from exc

        return JwtTokenPayload(
            user_id=user_id,
            username=username,
            role=role,
            force_password_change=force_password_change,
            expires_at=expires_at,
        )
