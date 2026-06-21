"""Unit tests for AuthService."""

import pytest
from sqlalchemy.orm import Session

from prm.application.auth_service import AuthService
from prm.domain.enums import Role, UserAccountStatus
from prm.domain.exceptions import AuthenticationError, UnauthorizedError, ValidationError
from prm.infrastructure.db.models import UserModel
from prm.infrastructure.db.repositories import SqlAlchemyUserRepository
from prm.infrastructure.db.seed import seed_bootstrap_admin
from prm.infrastructure.security.jwt import JwtTokenService
from prm.infrastructure.security.password import BcryptPasswordHasher
from tests.unit.credentials import TEST_EMAIL, TEST_FULL_NAME, TEST_PASSWORD, TEST_USERNAME
from tests.unit.engineer_fixtures import create_memory_session

JWT_SECRET = "auth-service-test-secret"


def _session() -> Session:
    return create_memory_session()


def _auth_service(session: Session) -> AuthService:
    return AuthService(
        user_repository=SqlAlchemyUserRepository(session),
        password_hasher=BcryptPasswordHasher(),
        token_service=JwtTokenService(secret_key=JWT_SECRET, expire_minutes=60),
    )


def _seed_admin(session: Session) -> None:
    seed_bootstrap_admin(
        session,
        username=TEST_USERNAME,
        password=TEST_PASSWORD,
        full_name=TEST_FULL_NAME,
        email=TEST_EMAIL,
    )


def test_login_success_returns_token_and_force_password_change_flag() -> None:
    with _session() as session:
        _seed_admin(session)
        result = _auth_service(session).login(TEST_USERNAME, TEST_PASSWORD)

        assert result.access_token
        assert result.token_type == "bearer"
        assert result.user_id == 1
        assert result.username == TEST_USERNAME
        assert result.role == Role.ADMIN
        assert result.force_password_change is True
        assert result.email_verified is True


def test_login_fails_with_wrong_password() -> None:
    with _session() as session:
        _seed_admin(session)
        with pytest.raises(AuthenticationError, match="Invalid username or password"):
            _auth_service(session).login(TEST_USERNAME, "WrongPass1")


def test_login_fails_with_unknown_username() -> None:
    with _session() as session:
        with pytest.raises(AuthenticationError, match="Invalid username or password"):
            _auth_service(session).login("nobody", "Password1")


def test_login_fails_for_inactive_account() -> None:
    with _session() as session:
        _seed_admin(session)
        admin = session.get(UserModel, 1)
        assert admin is not None
        admin.account_status = UserAccountStatus.INACTIVE
        session.commit()

        with pytest.raises(UnauthorizedError, match="inactive"):
            _auth_service(session).login(TEST_USERNAME, TEST_PASSWORD)


def test_change_password_clears_force_flag_and_returns_new_token() -> None:
    with _session() as session:
        _seed_admin(session)
        service = _auth_service(session)
        login = service.login(TEST_USERNAME, TEST_PASSWORD)
        assert login.force_password_change is True

        updated, result = service.change_password(
            login.user_id,
            new_password="NewSecure1",
            confirm_password="NewSecure1",
        )
        session.commit()

        assert updated.force_password_change is False
        assert result.force_password_change is False
        assert result.access_token != login.access_token

        hasher = BcryptPasswordHasher()
        assert hasher.verify("NewSecure1", updated.password_hash)


def test_change_password_fails_when_confirmation_mismatches() -> None:
    with _session() as session:
        _seed_admin(session)
        login = _auth_service(session).login(TEST_USERNAME, TEST_PASSWORD)

        with pytest.raises(ValidationError, match="do not match"):
            _auth_service(session).change_password(
                login.user_id,
                new_password="NewSecure1",
                confirm_password="Different1",
            )


def test_change_password_fails_when_password_too_weak() -> None:
    with _session() as session:
        _seed_admin(session)
        login = _auth_service(session).login(TEST_USERNAME, TEST_PASSWORD)

        with pytest.raises(ValidationError):
            _auth_service(session).change_password(
                login.user_id,
                new_password="weak",
                confirm_password="weak",
            )
