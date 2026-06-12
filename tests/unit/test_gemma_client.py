"""Unit tests for GemmaClient with mocked HTTP."""

import httpx
import pytest

from prm.domain.constants import DEFAULT_GEMMA_BASE_URL, DEFAULT_GEMMA_MODEL
from prm.domain.dtos import (
    RiskSummaryContext,
    SkillMatchCandidate,
    SkillMatchContext,
)
from prm.domain.enums import ProjectHealthStatus
from prm.domain.exceptions import LlmUnavailableError
from prm.infrastructure.llm.gemma_client import GemmaClient


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


def test_gemma_client_posts_to_generate_endpoint() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/generate"
        assert request.headers["apikey"] == "test-key"
        import json

        payload = json.loads(request.content.decode())
        assert payload["model"] == DEFAULT_GEMMA_MODEL
        assert payload["stream"] is False
        return httpx.Response(
            200,
            json={
                "model": DEFAULT_GEMMA_MODEL,
                "response": (
                    '{"matches":[{"user_id":14,'
                    '"user_name":"Dev Patel",'
                    '"reason":"Java skills with partial availability.",'
                    '"suggested_allocation_percent":25,'
                    '"free_hours_per_week":20}]}'
                ),
                "done": True,
            },
        )

    client = GemmaClient(
        "test-key",
        base_url=DEFAULT_GEMMA_BASE_URL,
        model=DEFAULT_GEMMA_MODEL,
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    results = client.rank_candidates(_context(), (_candidate(),))

    assert len(results) == 1
    assert results[0].user_id == 14


def test_gemma_client_summarize_risk_returns_text() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "response": "Project delivery looks stable with no major blockers.",
                "done": True,
            },
        )

    client = GemmaClient(
        "test-key",
        base_url=DEFAULT_GEMMA_BASE_URL,
        model=DEFAULT_GEMMA_MODEL,
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    summary = client.summarize_risk(_risk_context())

    assert "stable" in summary.lower()


def test_gemma_client_raises_on_http_error() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": "invalid api key"})

    client = GemmaClient(
        "test-key",
        base_url=DEFAULT_GEMMA_BASE_URL,
        model=DEFAULT_GEMMA_MODEL,
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    with pytest.raises(LlmUnavailableError, match="Gemma request failed"):
        client.summarize_risk(_risk_context())
