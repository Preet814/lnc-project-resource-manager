"""Unit tests for ValidationResult DTO."""

from prm.domain.dtos import ValidationResult


def test_validation_result_valid() -> None:
    result = ValidationResult(is_valid=True, message="OK", total_percent=50)
    assert result.is_valid is True
    assert result.message == "OK"
    assert result.total_percent == 50


def test_validation_result_invalid_without_total() -> None:
    result = ValidationResult(is_valid=False, message="Over-allocated")
    assert result.is_valid is False
    assert result.total_percent is None


def test_validation_result_over_allocation_message() -> None:
    result = ValidationResult(
        is_valid=False,
        message="Total utilisation would be 120%",
        total_percent=120,
    )
    assert result.total_percent == 120
