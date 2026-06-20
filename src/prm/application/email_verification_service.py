"""Email verification via one-time passcode sent over SMTP."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from prm.application.protocols import EmailSender, TokenService, UserRepository
from prm.domain.constants import (
    EMAIL_OTP_EXPIRY_MINUTES,
    EMAIL_OTP_LENGTH,
    EMAIL_OTP_MAX_ATTEMPTS,
    EMAIL_OTP_RESEND_SECONDS,
)
from prm.domain.dtos import LoginResult
from prm.domain.exceptions import AuthenticationError, ValidationError
from prm.infrastructure.db.repositories.email_verification_otp_repository import (
    SqlAlchemyEmailVerificationOtpRepository,
)
from prm.infrastructure.security.otp import generate_numeric_otp, hash_otp, verify_otp

_INVALID_OTP_MESSAGE = "Invalid or expired verification code."


class EmailVerificationService:
    """Send and confirm email OTP during user onboarding."""

    def __init__(
        self,
        user_repository: UserRepository,
        otp_repository: SqlAlchemyEmailVerificationOtpRepository,
        email_sender: EmailSender,
        token_service: TokenService,
        *,
        otp_secret: str,
        email_verification_required: bool = True,
    ) -> None:
        self._users = user_repository
        self._otps = otp_repository
        self._email = email_sender
        self._tokens = token_service
        self._otp_secret = otp_secret
        self._email_verification_required = email_verification_required

    def send_otp(self, user_id: int) -> None:
        if not self._email_verification_required:
            raise ValidationError("Email verification is disabled.")

        user = self._users.find_by_id(user_id)
        if user is None:
            raise AuthenticationError("User not found.")

        if user.email_verified:
            raise ValidationError("Email address is already verified.")

        if user.force_password_change:
            raise ValidationError("Change your password before verifying your email.")

        now = datetime.now(UTC)
        existing = self._otps.find_for_user(user_id)
        if existing is not None:
            last_sent = existing.last_sent_at
            if last_sent.tzinfo is None:
                last_sent = last_sent.replace(tzinfo=UTC)
            elapsed = (now - last_sent).total_seconds()
            if elapsed < EMAIL_OTP_RESEND_SECONDS:
                wait = int(EMAIL_OTP_RESEND_SECONDS - elapsed)
                raise ValidationError(
                    f"Please wait {wait} seconds before requesting another code."
                )

        otp = generate_numeric_otp(EMAIL_OTP_LENGTH)
        expires_at = now + timedelta(minutes=EMAIL_OTP_EXPIRY_MINUTES)
        self._otps.replace_for_user(
            user_id,
            otp_hash=hash_otp(otp=otp, secret=self._otp_secret),
            expires_at=expires_at,
        )
        self._email.send(
            to=user.email,
            subject="PRM: Verify your email address",
            body=(
                f"Hello {user.full_name},\n\n"
                f"Your PRM verification code is: {otp}\n\n"
                f"This code expires in {EMAIL_OTP_EXPIRY_MINUTES} minutes.\n"
                "If you did not request this, you can ignore this email.\n"
            ),
        )

    def confirm_otp(self, user_id: int, *, otp: str) -> LoginResult:
        if not self._email_verification_required:
            raise ValidationError("Email verification is disabled.")

        user = self._users.find_by_id(user_id)
        if user is None:
            raise AuthenticationError("User not found.")

        if user.email_verified:
            return self._login_result_for_user(user)

        if user.force_password_change:
            raise ValidationError("Change your password before verifying your email.")

        challenge = self._otps.find_for_user(user_id)
        if challenge is None:
            raise ValidationError(_INVALID_OTP_MESSAGE)

        now = datetime.now(UTC)
        expires_at = challenge.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)
        if now >= expires_at:
            raise ValidationError(_INVALID_OTP_MESSAGE)

        if challenge.attempts >= EMAIL_OTP_MAX_ATTEMPTS:
            raise ValidationError(
                "Too many failed attempts. Request a new verification code."
            )

        if not verify_otp(otp=otp.strip(), secret=self._otp_secret, expected_hash=challenge.otp_hash):
            self._otps.increment_attempts(user_id)
            raise ValidationError(_INVALID_OTP_MESSAGE)

        verified = self._users.update_email_verified(user_id, email_verified=True)
        self._otps.delete_for_user(user_id)
        return self._login_result_for_user(verified)

    def _login_result_for_user(self, user) -> LoginResult:
        token = self._tokens.create_access_token(
            user_id=user.id,
            username=user.username,
            role=user.role,
            force_password_change=user.force_password_change,
            email_verified=self._effective_email_verified(user),
        )
        return LoginResult(
            access_token=token.token,
            token_type="bearer",
            user_id=user.id,
            username=user.username,
            full_name=user.full_name,
            role=user.role,
            force_password_change=user.force_password_change,
            email_verified=self._effective_email_verified(user),
            expires_at=token.expires_at,
        )

    def _effective_email_verified(self, user) -> bool:
        if not self._email_verification_required:
            return True
        return user.email_verified
