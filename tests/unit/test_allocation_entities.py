"""Unit tests for Allocation overlap behavior (manager allocation PR)."""

from datetime import date

from prm.domain.entities.allocation import Allocation
from prm.domain.enums import AllocationStatus


def _allocation(
    *,
    from_date: date,
    to_date: date | None,
    allocation_id: int = 1,
    status: AllocationStatus = AllocationStatus.ACTIVE,
) -> Allocation:
    return Allocation(
        id=allocation_id,
        user_id=1,
        project_id=1,
        utilisation_percent=50,
        from_date=from_date,
        to_date=to_date,
        status=status,
        created_by_user_id=1,
    )


def test_overlaps_period_open_ended_allocation() -> None:
    allocation = _allocation(from_date=date(2026, 3, 1), to_date=None)
    assert allocation.overlaps_period(date(2026, 6, 1), date(2026, 6, 30)) is True
    assert allocation.overlaps_period(date(2026, 1, 1), date(2026, 2, 28)) is False


def test_overlaps_period_open_ended_request_period() -> None:
    allocation = _allocation(from_date=date(2026, 3, 1), to_date=date(2026, 6, 30))
    assert allocation.overlaps_period(date(2026, 5, 1), None) is True


def test_overlaps_period_bounded_non_overlap() -> None:
    allocation = _allocation(from_date=date(2026, 3, 1), to_date=date(2026, 6, 30))
    assert allocation.overlaps_period(date(2026, 7, 1), date(2026, 8, 31)) is False


def test_overlaps_period_bounded_overlap() -> None:
    allocation = _allocation(from_date=date(2026, 3, 1), to_date=date(2026, 6, 30))
    assert allocation.overlaps_period(date(2026, 6, 1), date(2026, 9, 30)) is True


def test_overlaps_period_ignores_ended_allocation() -> None:
    allocation = _allocation(
        from_date=date(2026, 3, 1),
        to_date=date(2026, 6, 30),
        status=AllocationStatus.ENDED,
    )
    assert allocation.overlaps_period(date(2026, 4, 1), date(2026, 5, 1)) is False


def test_overlaps_between_two_active_allocations() -> None:
    first = _allocation(from_date=date(2026, 3, 1), to_date=date(2026, 6, 30), allocation_id=1)
    second = _allocation(from_date=date(2026, 5, 1), to_date=date(2026, 8, 31), allocation_id=2)
    assert first.overlaps(second) is True


def test_overlaps_ignores_ended_other_allocation() -> None:
    active = _allocation(from_date=date(2026, 3, 1), to_date=date(2026, 6, 30), allocation_id=1)
    ended = _allocation(
        from_date=date(2026, 5, 1),
        to_date=date(2026, 8, 31),
        allocation_id=2,
        status=AllocationStatus.ENDED,
    )
    assert active.overlaps(ended) is False


def test_expected_hours_for_week_prorates_partial_allocation() -> None:
    allocation = Allocation(
        id=1,
        user_id=1,
        project_id=1,
        utilisation_percent=100,
        from_date=date(2026, 6, 12),
        to_date=date(2026, 6, 20),
        status=AllocationStatus.ACTIVE,
        created_by_user_id=1,
    )
    # Week Mon 8 - Sun 14 Jun: only Thu-Sun overlap would be 12-14 = 3 days -> 17 hrs
    assert allocation.expected_hours_for_week(date(2026, 6, 8), max_weekly_hours=40) == 17
    # Week Mon 15 - Sun 21 Jun: 15-20 = 6 days -> 34 hrs
    assert allocation.expected_hours_for_week(date(2026, 6, 15), max_weekly_hours=40) == 34
    # Week before allocation starts
    assert allocation.expected_hours_for_week(date(2026, 6, 1), max_weekly_hours=40) == 0


def test_expected_hours_for_week_uses_utilisation_percent() -> None:
    allocation = _allocation(from_date=date(2026, 3, 1), to_date=date(2026, 6, 30))
    assert allocation.expected_hours_for_week(date(2026, 5, 4), max_weekly_hours=40) == 20
