"""Construct EmailSender from application settings."""

from prm.api.settings import Settings
from prm.application.protocols import EmailSender
from prm.infrastructure.email.logging_sender import LoggingEmailSender
from prm.infrastructure.email.smtp_sender import SmtpEmailSender


def create_email_sender(settings: Settings) -> EmailSender:
    if not settings.smtp_enabled:
        return LoggingEmailSender()
    return SmtpEmailSender(
        host=settings.smtp_host,
        port=settings.smtp_port,
        username=settings.smtp_user,
        password=settings.smtp_password,
        from_address=settings.smtp_from,
        use_tls=settings.smtp_use_tls,
    )
