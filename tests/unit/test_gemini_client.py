"""Unit tests for GeminiClient with mocked HTTP."""

import httpx
import pytest

from prm.domain.constants import DEFAULT_GEMINI_BASE_URL, DEFAULT_GEMINI_MODEL
from prm.domain.dtos import (
    RiskSummaryContext,
    SkillMatchCandidate,
    SkillMatchContext,
)
from prm.domain.enums import ProjectHealthStatus
from prm.domain.exceptions import LlmUnavailableError
from prm.infrastructure.llm.gemini_client import GeminiClient


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


def _risk_context() -> RiskSummaryContext:
    return RiskSummaryContext(
        project_id=1,
        project_name="Alpha Portal",
        health_status=ProjectHealthStatus.AT_RISK,
        end_date=None,
        risk_flags=("Backend API milestone is overdue",),
        milestones=(),
        allocated_resources=(),
        recent_timesheets=(),
    )


def test_gemini_client_rank_candidates_parses_response() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert "generateContent" in str(request.url)
        return httpx.Response(
            200,
            json={
                "candidates": [
                    {
                        "content": {
                            "parts": [
                                {
                                    "text": (
                                        '{"matches":[{"user_id":12,'
                                        '"user_name":"Anil Mehta",'
                                        '"reason":"Strong microservices fit.",'
                                        '"suggested_allocation_percent":50,'
                                        '"free_hours_per_week":40}]}'
                                    )
                                }
                            ]
                        }
                    }
                ]
            },
        )

    client = GeminiClient(
        "test-key",
        base_url=DEFAULT_GEMINI_BASE_URL,
        model=DEFAULT_GEMINI_MODEL,
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    results = client.rank_candidates(_context(), (_candidate(),))

    assert len(results) == 1
    assert results[0].user_name == "Anil Mehta"


def test_gemini_client_summarize_risk_returns_text() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "candidates": [
                    {
                        "content": {
                            "parts": [
                                {"text": "The backend milestone is overdue and needs attention."}
                            ]
                        }
                    }
                ]
            },
        )

    client = GeminiClient(
        "test-key",
        base_url=DEFAULT_GEMINI_BASE_URL,
        model=DEFAULT_GEMINI_MODEL,
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    summary = client.summarize_risk(_risk_context())

    assert "overdue" in summary.lower()


def test_gemini_client_raises_on_http_error() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": "server error"})

    client = GeminiClient(
        "test-key",
        base_url=DEFAULT_GEMINI_BASE_URL,
        model=DEFAULT_GEMINI_MODEL,
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    with pytest.raises(LlmUnavailableError, match="Gemini request failed"):
        client.rank_candidates(_context(), (_candidate(),))
