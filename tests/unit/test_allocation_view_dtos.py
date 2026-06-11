"""Unit tests for admin allocation-view DTOs."""

from datetime import datetime

from prm.domain.dtos import AllocationListResult, AllocationSummary


def test_allocation_summary_fields() -> None:
    summary = AllocationSummary(
        allocation_id=1,
        user_id=102,
        user_full_name="Ravi Kumar",
        project_id=201,
        project_name="Alpha Portal",
        utilisation_percent=50,
        from_date=datetime(2026, 3, 1).date(),
        to_date=datetime(2026, 6, 30).date(),
    )

    assert summary.user_full_name == "Ravi Kumar"
    assert summary.project_name == "Alpha Portal"
    assert summary.utilisation_percent == 50
    assert summary.to_date == datetime(2026, 6, 30).date()


def test_allocation_list_result_stores_total() -> None:
    allocations = (
        AllocationSummary(
            1,
            102,
            "Ravi Kumar",
            201,
            "Alpha Portal",
            50,
            datetime(2026, 3, 1).date(),
            datetime(2026, 6, 30).date(),
        ),
        AllocationSummary(
            2,
            102,
            "Ravi Kumar",
            202,
            "Beta CRM",
            50,
            datetime(2026, 4, 1).date(),
            datetime(2026, 7, 31).date(),
        ),
        AllocationSummary(
            3,
            104,
            "Neha Joshi",
            201,
            "Alpha Portal",
            100,
            datetime(2026, 3, 1).date(),
            datetime(2026, 6, 30).date(),
        ),
    )
    result = AllocationListResult(allocations=allocations, total=3)

    assert len(result.allocations) == 3
    assert result.total == 3
