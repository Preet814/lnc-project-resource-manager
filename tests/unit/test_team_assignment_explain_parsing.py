"""Unit tests for team assignment explain response parsing."""

import pytest

from prm.domain.dtos import (
    TeamAssignmentExplainContext,
    TeamAssignmentExplainSlot,
    TeamSlotFilters,
)
from prm.domain.enums import ProficiencyLevel, ResourceWorkStatus
from prm.domain.exceptions import LlmUnavailableError
from prm.infrastructure.llm.team_assignment_explain_parsing import (
    parse_team_assignment_explain_response,
)


def _context() -> TeamAssignmentExplainContext:
    return TeamAssignmentExplainContext(
        project_id=1,
        project_name="Banking Portal",
        requirement="Need a Senior Java Developer",
        slots=(
            TeamAssignmentExplainSlot(
                slot_id=1,
                position=1,
                role_label="Senior Java Developer",
                filters=TeamSlotFilters(
                    skill_name="Java",
                    min_proficiency=ProficiencyLevel.ADVANCED,
                ),
                user_id=5,
                user_name="Ravi Kumar",
                suggested_allocation_percent=50,
                free_hours_per_week=40,
                utilisation_percent=0,
                work_status=ResourceWorkStatus.BENCH,
            ),
        ),
    )


def test_parse_team_assignment_explain_response_maps_reasons() -> None:
    raw = """
    {
      "reasons": [
        {
          "slot_id": 1,
          "position": 1,
          "user_id": 5,
          "reason": "Ravi has Advanced Java and is fully available on bench."
        }
      ]
    }
    """

    reasons = parse_team_assignment_explain_response(raw, _context())

    assert len(reasons) == 1
    assert reasons[0].reason.startswith("Ravi has Advanced Java")


def test_parse_team_assignment_explain_response_ignores_unknown_user_id() -> None:
    raw = """
    {
      "reasons": [
        {
          "slot_id": 1,
          "position": 1,
          "user_id": 99,
          "reason": "Should be ignored."
        }
      ]
    }
    """

    reasons = parse_team_assignment_explain_response(raw, _context())

    assert reasons == ()


def test_parse_team_assignment_explain_response_rejects_invalid_json() -> None:
    with pytest.raises(LlmUnavailableError, match="invalid team assignment explain"):
        parse_team_assignment_explain_response("not-json", _context())
