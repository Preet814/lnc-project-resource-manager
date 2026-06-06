"""Password strength rules (BRD §3.4 — 8+ chars, uppercase, number)."""

import re

from prm.domain.constants import MIN_PASSWORD_LENGTH
from prm.domain.exceptions import ValidationError

_UPPERCASE_RE = re.compile(r"[A-Z]")
_DIGIT_RE = re.compile(r"\d")


def validate_password_strength(password: str) -> None:
    """Raise ValidationError when password does not meet BRD requirements."""
    if len(password) < MIN_PASSWORD_LENGTH:
        raise ValidationError(
            f"Password must be at least {MIN_PASSWORD_LENGTH} characters."
        )
    if not _UPPERCASE_RE.search(password):
        raise ValidationError("Password must contain at least one uppercase letter.")
    if not _DIGIT_RE.search(password):
        raise ValidationError("Password must contain at least one number.")
