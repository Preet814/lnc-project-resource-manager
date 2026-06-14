"""SMTP email sender for transactional messages."""

from __future__ import annotations

import logging
import smtplib
from email.message import EmailMessage

logger = logging.getLogger(__name__)


class SmtpEmailSender:
    """Send plain-text email via SMTP (STARTTLS on port 587 by default)."""

    def __init__(
        self,
        *,
        host: str,
        port: int,
        username: str,
        password: str,
        from_address: str,
        use_tls: bool = True,
    ) -> None:
        self._host = host
        self._port = port
        self._username = username
        self._password = password
        self._from_address = from_address
        self._use_tls = use_tls

    def send(self, *, to: str, subject: str, body: str) -> None:
        message = EmailMessage()
        message["From"] = self._from_address
        message["To"] = to
        message["Subject"] = subject
        message.set_content(body)

        try:
            with smtplib.SMTP(self._host, self._port, timeout=30) as client:
                if self._use_tls:
                    client.starttls()
                if self._username:
                    client.login(self._username, self._password)
                client.send_message(message)
        except smtplib.SMTPException as exc:
            logger.exception("SMTP send failed to %s", to)
            raise RuntimeError(f"Failed to send email to {to}.") from exc

        logger.info("Email sent to %s subject=%r", to, subject)
