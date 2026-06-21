"""Email delivery adapters."""

from prm.infrastructure.email.factory import create_email_sender
from prm.infrastructure.email.logging_sender import LoggingEmailSender
from prm.infrastructure.email.smtp_sender import SmtpEmailSender

__all__ = [
    "LoggingEmailSender",
    "SmtpEmailSender",
    "create_email_sender",
]
