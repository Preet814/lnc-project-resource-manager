"""Overlap and 100% utilisation cap (DESIGN.md — single responsibility)."""

from datetime import date

from prm.application.protocols import AllocationRepository
from prm.domain.constants import MAX_UTILISATION_PERCENT
from prm.domain.dtos import ValidationResult


class UtilisationCalculator:
    """Validate allocation utilisation without persisting rows."""

    def __init__(self, allocation_repository: AllocationRepository) -> None:
        self._allocations = allocation_repository

    def validate_new_allocation(
        self,
        employee_id: int,
        utilisation_percent: int,
        date_from: date,
        date_to: date | None,
        *,
        exclude_allocation_id: int | None = None,
    ) -> ValidationResult:
        if utilisation_percent < 1 or utilisation_percent > MAX_UTILISATION_PERCENT:
            return ValidationResult(
                is_valid=False,
                message=(
                    f"Utilisation must be between 1 and {MAX_UTILISATION_PERCENT} percent."
                ),
            )

        if date_to is not None and date_from > date_to:
            return ValidationResult(
                is_valid=False,
                message="From date must be on or before to date.",
            )

        overlapping = self._allocations.find_overlapping(
            employee_id,
            date_from,
            date_to,
            exclude_allocation_id=exclude_allocation_id,
        )
        existing_total = sum(allocation.utilisation_percent for allocation in overlapping)
        total_percent = existing_total + utilisation_percent

        if total_percent > MAX_UTILISATION_PERCENT:
            return ValidationResult(
                is_valid=False,
                message=(
                    f"Total utilisation in this period would be {total_percent}% "
                    f"(maximum {MAX_UTILISATION_PERCENT}%)."
                ),
                total_percent=total_percent,
            )

        return ValidationResult(
            is_valid=True,
            message="Valid",
            total_percent=total_percent,
        )

    def compute_utilisation_on(self, employee_id: int, as_of: date) -> int:
        """Sum utilisation % from active allocations covering a single date."""
        active = self._allocations.find_active_by_employee(employee_id)
        return sum(
            allocation.utilisation_percent
            for allocation in active
            if allocation.is_active_on(as_of)
        )
