"""Unit tests for Monday-based week calendar helpers."""

from datetime import date

import pytest

from prm.domain.exceptions import ValidationError
from prm.domain.week_calendar import assert_monday_week_start, week_end, week_start_on_or_before


def test_week_start_on_or_before_returns_monday() -> None:
    # Wednesday 2026-05-13 -> Monday 2026-05-11
    assert week_start_on_or_before(date(2026, 5, 13)) == date(2026, 5, 11)


def test_week_start_on_or_before_when_reference_is_monday() -> None:
    monday = date(2026, 5, 11)
    assert week_start_on_or_before(monday) == monday


def test_week_end_returns_sunday() -> None:
    week_start = date(2026, 5, 11)
    assert week_end(week_start) == date(2026, 5, 17)


def test_assert_monday_week_start_accepts_monday() -> None:
    assert_monday_week_start(date(2026, 5, 11))


def test_assert_monday_week_start_rejects_non_monday() -> None:
    with pytest.raises(ValidationError, match="Monday"):
        assert_monday_week_start(date(2026, 5, 12))
