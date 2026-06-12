"""Process-wide handle to the active SchedulerRunner (when the API has started it)."""

from __future__ import annotations

from prm.scheduler.runner import SchedulerRunner

_runner: SchedulerRunner | None = None


def register_runner(runner: SchedulerRunner) -> None:
    global _runner
    _runner = runner


def unregister_runner() -> None:
    global _runner
    _runner = None


def get_runner() -> SchedulerRunner | None:
    return _runner


def reschedule_interval_hours(hours: int) -> None:
    """Apply a new scheduler tick interval without restarting the API."""
    runner = _runner
    if runner is not None:
        runner.update_interval_hours(hours)
