"""Unit tests for email verification OTP repository."""

from datetime import UTC, datetime, timedelta

from prm.infrastructure.db.models import EmailVerificationOtpModel
from prm.infrastructure.db.repositories import SqlAlchemyEmailVerificationOtpRepository
from prm.infrastructure.db.seed import seed_bootstrap_admin
from prm.infrastructure.security.otp import hash_otp, verify_otp
from tests.unit.credentials import TEST_EMAIL, TEST_FULL_NAME, TEST_PASSWORD, TEST_USERNAME
from tests.unit.engineer_fixtures import create_rbac_tables


def _session():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session

    engine = create_engine("sqlite:///:memory:")
    create_rbac_tables(engine)
    EmailVerificationOtpModel.__table__.create(engine, checkfirst=True)
    return Session(engine)


def test_replace_and_verify_otp_roundtrip() -> None:
    secret = "otp-test-secret"
    with _session() as session:
        seed_bootstrap_admin(
            session,
            username=TEST_USERNAME,
            password=TEST_PASSWORD,
            full_name=TEST_FULL_NAME,
            email=TEST_EMAIL,
        )
        repo = SqlAlchemyEmailVerificationOtpRepository(session)
        expires_at = datetime.now(UTC) + timedelta(minutes=10)
        otp = "123456"
        stored = repo.replace_for_user(
            1,
            otp_hash=hash_otp(otp=otp, secret=secret),
            expires_at=expires_at,
        )
        session.commit()

        assert stored.user_id == 1
        assert stored.attempts == 0
        assert verify_otp(otp=otp, secret=secret, expected_hash=stored.otp_hash)

        repo.delete_for_user(1)
        session.commit()
        assert repo.find_for_user(1) is None
