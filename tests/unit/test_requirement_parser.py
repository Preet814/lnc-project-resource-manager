"""Unit tests for requirement_parser."""

from prm.application.requirement_parser import parse_requested_hours_per_week


def test_parse_requested_hours_per_week_from_hrs_slash_week() -> None:
    assert parse_requested_hours_per_week("10 hrs/week, UI testing") == 10


def test_parse_requested_hours_per_week_from_hours_per_week() -> None:
    assert (
        parse_requested_hours_per_week("Need about 15 hours per week for backend work")
        == 15
    )


def test_parse_requested_hours_per_week_returns_none_for_full_time() -> None:
    assert (
        parse_requested_hours_per_week(
            "Java developer with microservices experience for three months"
        )
        is None
    )


def test_parse_requested_hours_per_week_ignores_zero_hour_match() -> None:
    assert parse_requested_hours_per_week("0 hrs/week support") is None
