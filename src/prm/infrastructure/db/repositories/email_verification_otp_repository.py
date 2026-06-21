"""Email verification OTP persistence."""

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from prm.infrastructure.db.models.email_verification_otp import EmailVerificationOtpModel


@dataclass(frozen=True, slots=True)
class EmailVerificationOtp:
    user_id: int
    otp_hash: str
    expires_at: datetime
    attempts: int
    last_sent_at: datetime


class SqlAlchemyEmailVerificationOtpRepository:
    """Store and validate one OTP challenge per user."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def find_for_user(self, user_id: int) -> EmailVerificationOtp | None:
        row = self._session.scalar(
            select(EmailVerificationOtpModel).where(
                EmailVerificationOtpModel.user_id == user_id
            )
        )
        if row is None:
            return None
        return _to_domain(row)

    def replace_for_user(
        self,
        user_id: int,
        *,
        otp_hash: str,
        expires_at: datetime,
    ) -> EmailVerificationOtp:
        existing = self._session.scalar(
            select(EmailVerificationOtpModel).where(
                EmailVerificationOtpModel.user_id == user_id
            )
        )
        now = datetime.now(UTC)
        if existing is None:
            model = EmailVerificationOtpModel(
                user_id=user_id,
                otp_hash=otp_hash,
                expires_at=expires_at,
                attempts=0,
                last_sent_at=now,
            )
            self._session.add(model)
            self._session.flush()
            return _to_domain(model)

        existing.otp_hash = otp_hash
        existing.expires_at = expires_at
        existing.attempts = 0
        existing.last_sent_at = now
        self._session.flush()
        return _to_domain(existing)

    def increment_attempts(self, user_id: int) -> EmailVerificationOtp:
        model = self._session.scalar(
            select(EmailVerificationOtpModel).where(
                EmailVerificationOtpModel.user_id == user_id
            )
        )
        if model is None:
            raise RuntimeError(f"No OTP record for user {user_id}.")
        model.attempts += 1
        self._session.flush()
        return _to_domain(model)

    def delete_for_user(self, user_id: int) -> None:
        model = self._session.scalar(
            select(EmailVerificationOtpModel).where(
                EmailVerificationOtpModel.user_id == user_id
            )
        )
        if model is not None:
            self._session.delete(model)
            self._session.flush()


def _to_domain(model: EmailVerificationOtpModel) -> EmailVerificationOtp:
    return EmailVerificationOtp(
        user_id=model.user_id,
        otp_hash=model.otp_hash,
        expires_at=model.expires_at,
        attempts=model.attempts,
        last_sent_at=model.last_sent_at,
    )
