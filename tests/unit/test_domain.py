"""Unit tests for domain layer primitives."""

import pytest

from prm.domain import constants
from prm.domain.exceptions import (
    AuthenticationError,
    DomainError,
    NotFoundError,
    UnauthorizedError,
    ValidationError,
)


def test_constants_match_brd_defaults() -> None:
    assert constants.DEFAULT_MAX_WEEKLY_HOURS == 40
    assert constants.DEFAULT_SCHEDULER_INTERVAL_HOURS == 4
    assert constants.MIN_PASSWORD_LENGTH == 8
    assert constants.MAX_UTILISATION_PERCENT == 100


@pytest.mark.parametrize(
    "exc_type",
    [
        ValidationError,
        UnauthorizedError,
        NotFoundError,
        AuthenticationError,
    ],
)
def test_domain_exceptions_inherit_from_domain_error(exc_type: type[DomainError]) -> None:
    assert issubclass(exc_type, DomainError)
    assert issubclass(exc_type, Exception)
