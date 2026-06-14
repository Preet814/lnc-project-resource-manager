#!/usr/bin/env python3
"""Send a test email using SMTP settings from .env."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from prm.api.settings import get_settings
from prm.infrastructure.email.factory import create_email_sender


def main() -> None:
    parser = argparse.ArgumentParser(description="Send a PRM SMTP test email.")
    parser.add_argument(
        "recipient",
        nargs="?",
        default=None,
        help="Recipient address (defaults to BOOTSTRAP_ADMIN_EMAIL)",
    )
    args = parser.parse_args()

    get_settings.cache_clear()
    settings = get_settings()
    recipient = args.recipient or settings.bootstrap_admin_email
    if not recipient:
        raise SystemExit("Provide recipient or set BOOTSTRAP_ADMIN_EMAIL in .env")

    sender = create_email_sender(settings)
    sender.send(
        to=recipient,
        subject="PRM SMTP test",
        body=(
            "This is a test message from the PRM application.\n\n"
            f"SMTP enabled: {settings.smtp_enabled}\n"
        ),
    )
    print(f"Test email sent to {recipient} (see API logs if SMTP_ENABLED=false).")


if __name__ == "__main__":
    main()
