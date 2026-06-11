"""Unit tests for GroqClient with mocked HTTP."""

import httpx
import pytest

from prm.domain.constants import DEFAULT_GROQ_BASE_URL, DEFAULT_GROQ_MODEL
from prm.domain.dtos import (
    RiskSummaryContext,
    SkillMatchCandidate,
    SkillMatchContext,
)
from prm.domain.enums import ProjectHealthStatus
from prm.domain.exceptions import LlmUnavailableError
from prm.infrastructure.llm.groq_client import GroqClient


def _candidate() -> SkillMatchCandidate:
    return SkillMatchCandidate(
        user_id=14,
        full_name="Dev Patel",
        skill_names=("Java", "Spring Boot"),
        utilisation_percent=50,
        free_hours_per_week=20,
        recent_activity_tags=("Backend API",),
    )


def _context() -> SkillMatchContext:
    return SkillMatchContext(
        project_id=2,
        project_name="Beta CRM",
        requirement="10 hrs/week backend support",
        requested_hours_per_week=10,
    )


def _risk_context() -> RiskSummaryContext:
    return RiskSummaryContext(
        project_id=2,
        project_name="Beta CRM",
        health_status=ProjectHealthStatus.ON_TRACK,
        end_date=None,
        risk_flags=(),
        milestones=(),
        allocated_resources=(),
        recent_timesheets=(),
    )


def test_groq_client_rank_candidates_parses_response() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/chat/completions")
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": (
                                '{"matches":[{"user_id":14,'
                                '"user_name":"Dev Patel",'
                                '"reason":"Java skills with partial availability.",'
                                '"suggested_allocation_percent":25,'
                                '"free_hours_per_week":20}]}'
                            )
                        }
                    }
                ]
            },
        )

    client = GroqClient(
        "test-key",
        base_url=DEFAULT_GROQ_BASE_URL,
        model=DEFAULT_GROQ_MODEL,
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    results = client.rank_candidates(_context(), (_candidate(),))

    assert len(results) == 1
    assert results[0].user_id == 14


def test_groq_client_summarize_risk_returns_text() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": "Project delivery looks stable with no major blockers."
                        }
                    }
                ]
            },
        )

    client = GroqClient(
        "test-key",
        base_url=DEFAULT_GROQ_BASE_URL,
        model=DEFAULT_GROQ_MODEL,
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    summary = client.summarize_risk(_risk_context())

    assert "stable" in summary.lower()


def test_groq_client_raises_on_http_error() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": "invalid api key"})

    client = GroqClient(
        "test-key",
        base_url=DEFAULT_GROQ_BASE_URL,
        model=DEFAULT_GROQ_MODEL,
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    with pytest.raises(LlmUnavailableError, match="Groq request failed"):
        client.summarize_risk(_risk_context())
