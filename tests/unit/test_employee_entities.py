"""Unit tests for employee, skill, and allocation domain entities."""

from datetime import UTC, datetime

from prm.domain.constants import MAX_UTILISATION_PERCENT
from prm.domain.entities.allocation import Allocation
from prm.domain.entities.employee import Employee
from prm.domain.enums import AllocationStatus, EmployeeWorkStatus


def _employee(*, work_status: EmployeeWorkStatus, utilisation: int) -> Employee:
    return Employee(
        id=1,
        user_id=4,
        full_name="Ravi Kumar",
        email="ravi@example.com",
        department="Backend",
        designation="Senior Developer",
        work_status=work_status,
        is_active=True,
        current_utilisation_percent=utilisation,
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
    )


def test_employee_is_on_bench() -> None:
    bench = _employee(work_status=EmployeeWorkStatus.BENCH, utilisation=0)
    allocated = _employee(work_status=EmployeeWorkStatus.ALLOCATED, utilisation=50)

    assert bench.is_on_bench() is True
    assert allocated.is_on_bench() is False


def test_employee_is_over_utilised() -> None:
    normal = _employee(work_status=EmployeeWorkStatus.ALLOCATED, utilisation=100)
    over = _employee(
        work_status=EmployeeWorkStatus.ALLOCATED,
        utilisation=MAX_UTILISATION_PERCENT + 1,
    )

    assert normal.is_over_utilised() is False
    assert over.is_over_utilised() is True


def test_allocation_is_active_on() -> None:
    allocation = Allocation(
        id=1,
        employee_id=1,
        project_id=10,
        utilisation_percent=50,
        from_date=datetime(2026, 6, 1).date(),
        to_date=datetime(2026, 6, 30).date(),
        status=AllocationStatus.ACTIVE,
        created_by_user_id=2,
    )

    assert allocation.is_active_on(datetime(2026, 6, 15).date()) is True
    assert allocation.is_active_on(datetime(2026, 5, 31).date()) is False
    assert allocation.is_active_on(datetime(2026, 7, 1).date()) is False

    ended = Allocation(
        id=2,
        employee_id=1,
        project_id=11,
        utilisation_percent=50,
        from_date=datetime(2026, 6, 1).date(),
        to_date=None,
        status=AllocationStatus.ENDED,
        created_by_user_id=2,
    )
    assert ended.is_active_on(datetime(2026, 6, 15).date()) is False
