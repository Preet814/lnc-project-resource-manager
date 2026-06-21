"""Unit tests for user, skill, and allocation domain entities."""

from datetime import UTC, datetime

from prm.domain.entities.allocation import Allocation
from prm.domain.entities.user import User
from prm.domain.enums import AllocationStatus, ResourceWorkStatus, Role, UserAccountStatus


def _engineer(*, work_status: ResourceWorkStatus, utilisation: int) -> User:
    return User(
        id=1,
        full_name="Ravi Kumar",
        username="ravi",
        email="ravi@example.com",
        password_hash="hash",
        role_id=1,
        role=Role.ENGINEER,
        department_id=1,
        designation_id=1,
        manager_id=None,
        account_status=UserAccountStatus.ACTIVE,
        force_password_change=False,
        email_verified=True,
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        updated_at=datetime(2026, 1, 1, tzinfo=UTC),
        department_name="Backend",
        designation_name="Senior Developer",
        work_status=work_status,
        utilisation_percent=utilisation,
    )


def test_user_is_on_bench() -> None:
    bench = _engineer(work_status=ResourceWorkStatus.BENCH, utilisation=0)
    allocated = _engineer(work_status=ResourceWorkStatus.ALLOCATED, utilisation=50)

    assert bench.is_on_bench() is True
    assert allocated.is_on_bench() is False


def test_user_is_engineer() -> None:
    engineer = _engineer(work_status=ResourceWorkStatus.BENCH, utilisation=0)
    assert engineer.is_engineer() is True


def test_allocation_is_active_on() -> None:
    allocation = Allocation(
        id=1,
        user_id=1,
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
        user_id=1,
        project_id=11,
        utilisation_percent=50,
        from_date=datetime(2026, 6, 1).date(),
        to_date=None,
        status=AllocationStatus.ENDED,
        created_by_user_id=2,
    )
    assert ended.is_active_on(datetime(2026, 6, 15).date()) is False
