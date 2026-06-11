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
