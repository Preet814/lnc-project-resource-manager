"""Unit tests for FakeLlmClient."""

import pytest

from prm.domain.dtos import (
    RiskSummaryContext,
    SkillMatchCandidate,
    SkillMatchContext,
    SkillMatchResult,
    TeamAssignmentExplainContext,
    TeamAssignmentExplainSlot,
    TeamAssignmentReason,
    TeamPlan,
    TeamPlanParseContext,
    TeamSlotFilters,
    TeamSlotSpec,
)
from prm.domain.enums import (
    ProficiencyLevel,
    ProjectHealthStatus,
    ResourceWorkStatus,
    SkillCategory,
)
from prm.domain.exceptions import LlmUnavailableError
from prm.infrastructure.llm.fake_client import FakeLlmClient


def _candidate() -> SkillMatchCandidate:
    return SkillMatchCandidate(
        user_id=12,
        full_name="Anil Mehta",
        skill_names=("Microservices",),
        utilisation_percent=0,
        free_hours_per_week=40,
        recent_activity_tags=("Microservices",),
    )


def _context() -> SkillMatchContext:
    return SkillMatchContext(
        project_id=1,
        project_name="Alpha Portal",
        requirement="Java microservices developer",
        requested_hours_per_week=None,
    )


def test_fake_llm_client_returns_preset_rank_results() -> None:
    fake = FakeLlmClient(
        rank_results=(
            SkillMatchResult(
                user_id=12,
                user_name="Anil Mehta",
                reason="Best fit",
                suggested_allocation_percent=50,
                free_hours_per_week=40,
            ),
        ),
    )

    results = fake.rank_candidates(_context(), (_candidate(),))

    assert len(results) == 1
    assert len(fake.rank_calls) == 1


def test_fake_llm_client_returns_empty_for_no_candidates() -> None:
    fake = FakeLlmClient()

    results = fake.rank_candidates(_context(), ())

    assert results == ()


def test_fake_llm_client_returns_preset_risk_summary() -> None:
    fake = FakeLlmClient(risk_summary="Backend milestone is overdue.")
    context = RiskSummaryContext(
        project_id=1,
        project_name="Alpha Portal",
        health_status=ProjectHealthStatus.AT_RISK,
        end_date=None,
        risk_flags=(),
        milestones=(),
        allocated_resources=(),
        recent_timesheets=(),
    )

    summary = fake.summarize_risk(context)

    assert summary == "Backend milestone is overdue."
    assert len(fake.risk_calls) == 1


def test_fake_llm_client_can_simulate_failures() -> None:
    fake = FakeLlmClient(fail_rank=True)

    with pytest.raises(LlmUnavailableError, match="Fake LLM rank failure"):
        fake.rank_candidates(_context(), (_candidate(),))


def test_fake_llm_client_returns_preset_team_plan() -> None:
    plan = TeamPlan(
        team_slots=(
            TeamSlotSpec(
                slot_id=1,
                role_label="QA Tester",
                headcount=1,
                filters=TeamSlotFilters(
                    skill_category=SkillCategory.QA,
                    skill_name="Manual Testing",
                    min_proficiency=ProficiencyLevel.INTERMEDIATE,
                ),
            ),
        ),
    )
    fake = FakeLlmClient(team_plan=plan)
    context = TeamPlanParseContext(
        project_id=1,
        project_name="Banking Portal",
        requirement="Need a QA tester",
    )

    parsed = fake.parse_team_plan(context)

    assert parsed == plan
    assert len(fake.parse_team_plan_calls) == 1


def test_fake_llm_client_returns_preset_explain_reasons() -> None:
    context = TeamAssignmentExplainContext(
        project_id=1,
        project_name="Banking Portal",
        requirement="Need a Java developer",
        slots=(
            TeamAssignmentExplainSlot(
                slot_id=1,
                position=1,
                role_label="Java Developer",
                filters=TeamSlotFilters(skill_name="Java"),
                user_id=5,
                user_name="Ravi Kumar",
                suggested_allocation_percent=50,
                free_hours_per_week=40,
                utilisation_percent=0,
                work_status=ResourceWorkStatus.BENCH,
            ),
        ),
    )
    fake = FakeLlmClient(
        explain_reasons=(
            TeamAssignmentReason(
                slot_id=1,
                position=1,
                user_id=5,
                reason="Advanced Java skills with full bench availability.",
            ),
        ),
    )

    reasons = fake.explain_team_assignments(context)

    assert reasons[0].reason == "Advanced Java skills with full bench availability."
    assert len(fake.explain_team_assignments_calls) == 1


def test_fake_llm_client_can_simulate_explain_failure() -> None:
    fake = FakeLlmClient(fail_explain_team_assignments=True)
    context = TeamAssignmentExplainContext(
        project_id=1,
        project_name="Banking Portal",
        requirement="Need a Java developer",
        slots=(),
    )

    with pytest.raises(LlmUnavailableError, match="team assignment explain failure"):
        fake.explain_team_assignments(context)
