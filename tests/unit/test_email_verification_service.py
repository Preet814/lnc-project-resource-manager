"""Unit tests for EmailVerificationService."""

import re

import pytest
from sqlalchemy.orm import Session

from prm.application.email_verification_service import EmailVerificationService
from prm.domain.enums import Role, UserAccountStatus
from prm.domain.exceptions import ValidationError
from prm.infrastructure.db.models import EmailVerificationOtpModel
from prm.infrastructure.db.repositories import (
    SqlAlchemyEmailVerificationOtpRepository,
    SqlAlchemyUserRepository,
)
from prm.infrastructure.db.rbac_seed import (
    default_department_id,
    default_designation_id,
    role_id_for_code,
    seed_rbac_lookups,
)
from prm.infrastructure.security.jwt import JwtTokenService
from prm.infrastructure.security.password import BcryptPasswordHasher
from tests.unit.engineer_fixtures import create_memory_session

OTP_SECRET = "email-verification-test-secret"


class FakeEmailSender:
    def __init__(self) -> None:
        self.messages: list[tuple[str, str, str]] = []

    def send(self, *, to: str, subject: str, body: str) -> None:
        self.messages.append((to, subject, body))


def _service(session: Session, email_sender: FakeEmailSender) -> EmailVerificationService:
    return EmailVerificationService(
        user_repository=SqlAlchemyUserRepository(session),
        otp_repository=SqlAlchemyEmailVerificationOtpRepository(session),
        email_sender=email_sender,
        token_service=JwtTokenService(secret_key=OTP_SECRET, expire_minutes=60),
        otp_secret=OTP_SECRET,
        email_verification_required=True,
    )


def _create_unverified_engineer(session: Session) -> int:
    seed_rbac_lookups(session)
    hasher = BcryptPasswordHasher()
    created = SqlAlchemyUserRepository(session).create(
        full_name="Chinmay Jain",
        username="chinmay",
        email="chinmay@gmail.com",
        password_hash=hasher.hash("TempPass1"),
        role_id=role_id_for_code(session, Role.ENGINEER.value),
        department_id=default_department_id(session, name="Backend"),
        designation_id=default_designation_id(session, name="SE"),
        manager_id=None,
        force_password_change=False,
        account_status=UserAccountStatus.ACTIVE,
    )
    session.flush()
    return created.id


def _extract_otp(body: str) -> str:
    match = re.search(r"verification code is: (\d+)", body)
    assert match is not None
    return match.group(1)


def test_send_and_confirm_otp_marks_user_verified() -> None:
    with create_memory_session() as session:
        EmailVerificationOtpModel.__table__.create(session.get_bind(), checkfirst=True)
        user_id = _create_unverified_engineer(session)
        sender = FakeEmailSender()
        service = _service(session, sender)

        service.send_otp(user_id)
        session.commit()

        assert len(sender.messages) == 1
        assert sender.messages[0][0] == "chinmay@gmail.com"
        otp = _extract_otp(sender.messages[0][2])

        result = service.confirm_otp(user_id, otp=otp)
        session.commit()

        assert result.email_verified is True
        user = SqlAlchemyUserRepository(session).find_by_id(user_id)
        assert user is not None
        assert user.email_verified is True


def test_send_otp_rejected_while_password_change_required() -> None:
    with create_memory_session() as session:
        EmailVerificationOtpModel.__table__.create(session.get_bind(), checkfirst=True)
        user_id = _create_unverified_engineer(session)
        repo = SqlAlchemyUserRepository(session)
        repo.update_password(
            user_id,
            password_hash=BcryptPasswordHasher().hash("TempPass1"),
            force_password_change=True,
        )
        session.flush()

        service = _service(session, FakeEmailSender())
        with pytest.raises(ValidationError, match="Change your password"):
            service.send_otp(user_id)


def test_confirm_otp_rejects_invalid_code() -> None:
    with create_memory_session() as session:
        EmailVerificationOtpModel.__table__.create(session.get_bind(), checkfirst=True)
        user_id = _create_unverified_engineer(session)
        sender = FakeEmailSender()
        service = _service(session, sender)
        service.send_otp(user_id)
        session.commit()

        with pytest.raises(ValidationError, match="Invalid or expired"):
            service.confirm_otp(user_id, otp="000000")
