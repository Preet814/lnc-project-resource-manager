"""Unit tests for FakeLlmClient."""

import pytest

from prm.domain.dtos import (
    RiskSummaryContext,
    SkillMatchCandidate,
    SkillMatchContext,
    SkillMatchResult,
)
from prm.domain.enums import ProjectHealthStatus
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
