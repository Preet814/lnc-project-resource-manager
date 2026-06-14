"""Log-only email sender for local development."""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


class LoggingEmailSender:
    """Write email payloads to the application log instead of SMTP."""

    def send(self, *, to: str, subject: str, body: str) -> None:
        logger.info(
            "EMAIL (log-only) to=%s subject=%r\n%s",
            to,
            subject,
            body,
        )
