"""Unit tests for Monday-based week calendar helpers."""

from datetime import date

import pytest

from prm.domain.exceptions import ValidationError
from prm.domain.week_calendar import (
    assert_monday_week_start,
    last_completed_week_start,
    prorated_hours_for_overlap,
    week_end,
    week_start_on_or_before,
)


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


def test_last_completed_week_start_when_reference_is_mid_week() -> None:
    # Thursday 2026-06-11 -> last completed week starts Monday 2026-06-01
    assert last_completed_week_start(date(2026, 6, 11)) == date(2026, 6, 1)


def test_last_completed_week_start_on_monday_after_week_ends() -> None:
    # Monday 2026-06-22: week Mon 15 - Sun 21 just ended
    assert last_completed_week_start(date(2026, 6, 22)) == date(2026, 6, 15)


def test_prorated_hours_for_overlap_scales_linearly() -> None:
    assert prorated_hours_for_overlap(40, 3) == 17
    assert prorated_hours_for_overlap(40, 6) == 34
    assert prorated_hours_for_overlap(40, 0) == 0
