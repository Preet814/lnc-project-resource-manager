"""Unit tests for LLM skill match and risk summary DTOs."""

from datetime import date

from prm.domain.dtos import (
    RiskSummaryContext,
    RiskSummaryMilestoneFact,
    RiskSummaryResourceFact,
    RiskSummaryTimesheetFact,
    SkillMatchCandidate,
    SkillMatchContext,
    SkillMatchListResult,
    SkillMatchResult,
)
from prm.domain.enums import MilestoneStatus, ProjectHealthStatus


def test_skill_match_candidate_fields() -> None:
    candidate = SkillMatchCandidate(
        user_id=12,
        full_name="Anil Mehta",
        skill_names=("Microservices", "Docker"),
        utilisation_percent=0,
        free_hours_per_week=40,
        recent_activity_tags=("Microservices",),
    )

    assert candidate.full_name == "Anil Mehta"
    assert candidate.free_hours_per_week == 40
    assert candidate.skill_names == ("Microservices", "Docker")


def test_skill_match_context_part_time_request() -> None:
    context = SkillMatchContext(
        project_id=1,
        project_name="Alpha Portal",
        requirement="10 hrs/week, UI testing",
        requested_hours_per_week=10,
    )

    assert context.requested_hours_per_week == 10
    assert context.project_name == "Alpha Portal"


def test_skill_match_list_result_with_matches() -> None:
    matches = (
        SkillMatchResult(
            user_id=12,
            user_name="Anil Mehta",
            reason="Microservices skills and fully available on bench.",
            suggested_allocation_percent=25,
            free_hours_per_week=40,
        ),
        SkillMatchResult(
            user_id=14,
            user_name="Dev Patel",
            reason="Java background with partial availability.",
            suggested_allocation_percent=50,
            free_hours_per_week=20,
        ),
    )
    result = SkillMatchListResult(
        project_id=1,
        requirement="Java developer with microservices experience",
        matches=matches,
        total=2,
    )

    assert result.total == 2
    assert result.message is None
    assert result.matches[0].suggested_allocation_percent == 25


def test_skill_match_list_result_without_matches() -> None:
    result = SkillMatchListResult(
        project_id=1,
        requirement="20 hrs/week, backend API work",
        matches=(),
        total=0,
        message="No engineers have at least 20 free hours per week.",
    )

    assert result.total == 0
    assert result.matches == ()
    assert result.message is not None


def test_risk_summary_context_fields() -> None:
    context = RiskSummaryContext(
        project_id=1,
        project_name="Alpha Portal",
        health_status=ProjectHealthStatus.AT_RISK,
        end_date=date(2026, 6, 30),
        risk_flags=(
            "Backend API milestone is 5 days overdue",
            "Ravi Kumar logged only 4 hrs last week (expected 20 hrs)",
        ),
        milestones=(
            RiskSummaryMilestoneFact(
                title="Backend API",
                due_date=date(2026, 4, 15),
                status=MilestoneStatus.IN_PROGRESS,
                is_overdue=True,
            ),
        ),
        allocated_resources=(
            RiskSummaryResourceFact(
                user_full_name="Ravi Kumar",
                utilisation_percent=50,
            ),
        ),
        recent_timesheets=(
            RiskSummaryTimesheetFact(
                user_full_name="Ravi Kumar",
                week_start_date=date(2026, 5, 5),
                hours_logged=4,
                expected_hours=20,
            ),
        ),
    )

    assert context.health_status == ProjectHealthStatus.AT_RISK
    assert context.milestones[0].is_overdue is True
    assert context.recent_timesheets[0].hours_logged == 4
    assert context.recent_timesheets[0].expected_hours == 20


def test_risk_summary_result_fields() -> None:
    from prm.domain.constants import AI_RISK_SUMMARY_DISCLAIMER
    from prm.domain.dtos import RiskSummaryResult

    result = RiskSummaryResult(
        project_id=1,
        summary="The backend milestone is overdue.",
        disclaimer=AI_RISK_SUMMARY_DISCLAIMER,
    )

    assert result.project_id == 1
    assert "overdue" in result.summary.lower()
