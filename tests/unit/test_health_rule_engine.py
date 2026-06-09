"""Unit tests for HealthRuleEngine."""

from datetime import date

from prm.application.health_rule_engine import HealthRuleEngine
from prm.domain.constants import HEALTH_RESOURCES_ALLOCATED_FLAG
from prm.domain.dtos import (
    HealthEvaluationInput,
    HealthMilestoneFact,
    HealthTimesheetFact,
)
from prm.domain.enums import MilestoneStatus, ProjectHealthStatus


def _engine() -> HealthRuleEngine:
    return HealthRuleEngine()


def test_evaluate_on_track_with_allocations_adds_positive_flag() -> None:
    result = _engine().evaluate(
        HealthEvaluationInput(
            as_of=date(2026, 5, 20),
            milestones=(),
            last_week_timesheets=(
                HealthTimesheetFact(
                    employee_full_name="Ravi Kumar",
                    hours_logged=20,
                    expected_hours=20,
                ),
            ),
            has_active_allocations=True,
        )
    )

    assert result.status == ProjectHealthStatus.ON_TRACK
    assert result.risk_flags == (HEALTH_RESOURCES_ALLOCATED_FLAG,)


def test_evaluate_on_track_without_allocations_has_no_positive_flag() -> None:
    result = _engine().evaluate(
        HealthEvaluationInput(
            as_of=date(2026, 5, 20),
            milestones=(),
            last_week_timesheets=(),
            has_active_allocations=False,
        )
    )

    assert result.status == ProjectHealthStatus.ON_TRACK
    assert result.risk_flags == ()


def test_evaluate_at_risk_for_overdue_milestone() -> None:
    result = _engine().evaluate(
        HealthEvaluationInput(
            as_of=date(2026, 4, 20),
            milestones=(
                HealthMilestoneFact(
                    title="Backend API",
                    due_date=date(2026, 4, 15),
                    status=MilestoneStatus.IN_PROGRESS,
                ),
            ),
            last_week_timesheets=(),
            has_active_allocations=True,
        )
    )

    assert result.status == ProjectHealthStatus.AT_RISK
    assert result.risk_flags[0] == "Backend API milestone is 5 days overdue"
    assert HEALTH_RESOURCES_ALLOCATED_FLAG in result.risk_flags


def test_evaluate_ignores_done_milestones_past_due_date() -> None:
    result = _engine().evaluate(
        HealthEvaluationInput(
            as_of=date(2026, 4, 20),
            milestones=(
                HealthMilestoneFact(
                    title="Backend API",
                    due_date=date(2026, 4, 15),
                    status=MilestoneStatus.DONE,
                ),
            ),
            last_week_timesheets=(),
            has_active_allocations=False,
        )
    )

    assert result.status == ProjectHealthStatus.ON_TRACK
    assert result.risk_flags == ()


def test_evaluate_at_risk_for_severely_low_hours() -> None:
    result = _engine().evaluate(
        HealthEvaluationInput(
            as_of=date(2026, 5, 20),
            milestones=(),
            last_week_timesheets=(
                HealthTimesheetFact(
                    employee_full_name="Ravi Kumar",
                    hours_logged=4,
                    expected_hours=20,
                ),
            ),
            has_active_allocations=True,
        )
    )

    assert result.status == ProjectHealthStatus.AT_RISK
    assert (
        "Ravi Kumar logged only 4 hrs last week (expected 20 hrs)" in result.risk_flags
    )


def test_evaluate_attention_for_moderately_low_hours() -> None:
    result = _engine().evaluate(
        HealthEvaluationInput(
            as_of=date(2026, 5, 20),
            milestones=(),
            last_week_timesheets=(
                HealthTimesheetFact(
                    employee_full_name="Neha Joshi",
                    hours_logged=12,
                    expected_hours=20,
                ),
            ),
            has_active_allocations=True,
        )
    )

    assert result.status == ProjectHealthStatus.ATTENTION
    assert (
        "Neha Joshi logged only 12 hrs last week (expected 20 hrs)" in result.risk_flags
    )


def test_evaluate_at_risk_when_overdue_and_low_hours() -> None:
    result = _engine().evaluate(
        HealthEvaluationInput(
            as_of=date(2026, 5, 20),
            milestones=(
                HealthMilestoneFact(
                    title="Backend API",
                    due_date=date(2026, 5, 15),
                    status=MilestoneStatus.IN_PROGRESS,
                ),
            ),
            last_week_timesheets=(
                HealthTimesheetFact(
                    employee_full_name="Ravi Kumar",
                    hours_logged=4,
                    expected_hours=20,
                ),
            ),
            has_active_allocations=True,
        )
    )

    assert result.status == ProjectHealthStatus.AT_RISK
    assert result.risk_flags[0] == "Backend API milestone is 5 days overdue"
    assert (
        "Ravi Kumar logged only 4 hrs last week (expected 20 hrs)" in result.risk_flags
    )
    assert HEALTH_RESOURCES_ALLOCATED_FLAG in result.risk_flags


def test_evaluate_skips_low_hours_check_when_expected_hours_is_zero() -> None:
    result = _engine().evaluate(
        HealthEvaluationInput(
            as_of=date(2026, 5, 20),
            milestones=(),
            last_week_timesheets=(
                HealthTimesheetFact(
                    employee_full_name="Bench User",
                    hours_logged=0,
                    expected_hours=0,
                ),
            ),
            has_active_allocations=False,
        )
    )

    assert result.status == ProjectHealthStatus.ON_TRACK
    assert result.risk_flags == ()
