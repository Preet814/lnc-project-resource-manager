"""Unit tests for LLM response parsing helpers."""

import pytest

from prm.domain.dtos import SkillMatchCandidate
from prm.domain.exceptions import LlmUnavailableError
from prm.infrastructure.llm.parsing import extract_json_text, parse_skill_match_response


def test_extract_json_text_strips_markdown_fence() -> None:
    raw = '```json\n{"matches": []}\n```'

    assert extract_json_text(raw) == '{"matches": []}'


def test_parse_skill_match_response_maps_valid_payload() -> None:
    candidates = (
        SkillMatchCandidate(
            employee_id=12,
            full_name="Anil Mehta",
            skill_names=("Microservices",),
            utilisation_percent=0,
            free_hours_per_week=40,
            recent_activity_tags=("Microservices",),
        ),
    )
    raw = """
    {
      "matches": [
        {
          "employee_id": 12,
          "employee_name": "Anil Mehta",
          "reason": "Strong microservices fit and fully available.",
          "suggested_allocation_percent": 50,
          "free_hours_per_week": 40
        }
      ]
    }
    """

    results = parse_skill_match_response(raw, candidates)

    assert len(results) == 1
    assert results[0].employee_id == 12
    assert results[0].suggested_allocation_percent == 50


def test_parse_skill_match_response_ignores_unknown_employee_ids() -> None:
    candidates = (
        SkillMatchCandidate(
            employee_id=12,
            full_name="Anil Mehta",
            skill_names=("Microservices",),
            utilisation_percent=0,
            free_hours_per_week=40,
            recent_activity_tags=(),
        ),
    )
    raw = """
    {
      "matches": [
        {
          "employee_id": 99,
          "employee_name": "Unknown",
          "reason": "Should be ignored",
          "suggested_allocation_percent": 25,
          "free_hours_per_week": 10
        }
      ]
    }
    """

    results = parse_skill_match_response(raw, candidates)

    assert results == ()


def test_parse_skill_match_response_rejects_invalid_json() -> None:
    with pytest.raises(LlmUnavailableError, match="invalid skill match response"):
        parse_skill_match_response("not-json", ())
