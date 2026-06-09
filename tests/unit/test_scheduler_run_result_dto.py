"""Unit tests for scheduler run result DTO."""

from prm.domain.dtos import SchedulerRunResult


def test_scheduler_run_result() -> None:
    result = SchedulerRunResult(
        employees_synced=3,
        projects_evaluated=2,
        missed_weeks_created=1,
    )

    assert result.employees_synced == 3
    assert result.projects_evaluated == 2
    assert result.missed_weeks_created == 1
