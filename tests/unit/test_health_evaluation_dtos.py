"""Unit tests for scheduler health evaluation DTOs."""

from datetime import date

from prm.domain.dtos import (
    HealthEvaluationInput,
    HealthEvaluationResult,
    HealthMilestoneFact,
    HealthTimesheetFact,
)
from prm.domain.enums import MilestoneStatus, ProjectHealthStatus


def test_health_evaluation_input() -> None:
    facts = HealthEvaluationInput(
        as_of=date(2026, 5, 20),
        milestones=(
            HealthMilestoneFact(
                title="Backend API",
                due_date=date(2026, 4, 15),
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

    assert facts.as_of == date(2026, 5, 20)
    assert facts.milestones[0].title == "Backend API"
    assert facts.last_week_timesheets[0].expected_hours == 20
    assert facts.has_active_allocations is True


def test_health_evaluation_result() -> None:
    result = HealthEvaluationResult(
        status=ProjectHealthStatus.AT_RISK,
        risk_flags=(
            "Backend API milestone is 5 days overdue",
            "Resources are correctly allocated",
        ),
    )

    assert result.status == ProjectHealthStatus.AT_RISK
    assert len(result.risk_flags) == 2
