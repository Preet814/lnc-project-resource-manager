"""Unit tests for password strength validation."""

import pytest

from prm.domain.exceptions import ValidationError
from prm.domain.password_policy import validate_password_strength


def test_valid_password_passes() -> None:
    validate_password_strength("Admin@1234")


@pytest.mark.parametrize(
    "password",
    [
        "short1A",
        "alllowercase1",
        "NoDigitsHere",
        "",
    ],
)
def test_invalid_password_raises(password: str) -> None:
    with pytest.raises(ValidationError):
        validate_password_strength(password)
