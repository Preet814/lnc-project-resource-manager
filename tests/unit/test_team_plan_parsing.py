"""Unit tests for team plan LLM response parsing."""

import pytest

from prm.domain.enums import (
    ActivityTag,
    ProficiencyLevel,
    ResourceWorkStatus,
    SkillCategory,
)
from prm.domain.exceptions import LlmUnavailableError
from prm.infrastructure.llm.team_plan_parsing import parse_team_plan_response


def test_parse_team_plan_response_maps_banking_portal_slots() -> None:
    raw = """
    {
      "team_slots": [
        {
          "slot_id": 1,
          "role_label": "Senior Java Developer",
          "headcount": 1,
          "filters": {
            "department": null,
            "designation": null,
            "skill_category": "BACKEND",
            "skill_name": "Java",
            "min_proficiency": "ADVANCED",
            "min_free_hours_per_week": null,
            "activity_tags": [],
            "work_status": null
          }
        },
        {
          "slot_id": 2,
          "role_label": "DevOps Engineer",
          "headcount": 1,
          "filters": {
            "department": null,
            "designation": null,
            "skill_category": "DEVOPS",
            "skill_name": "Docker",
            "min_proficiency": "INTERMEDIATE",
            "min_free_hours_per_week": 20,
            "activity_tags": ["DEVOPS"],
            "work_status": null
          }
        }
      ]
    }
    """

    plan = parse_team_plan_response(raw)

    assert len(plan.team_slots) == 2
    java_slot = plan.team_slots[0]
    assert java_slot.role_label == "Senior Java Developer"
    assert java_slot.headcount == 1
    assert java_slot.filters.skill_category == SkillCategory.BACKEND
    assert java_slot.filters.skill_name == "Java"
    assert java_slot.filters.min_proficiency == ProficiencyLevel.ADVANCED
    assert java_slot.filters.activity_tags == ()

    devops_slot = plan.team_slots[1]
    assert devops_slot.filters.min_free_hours_per_week == 20
    assert devops_slot.filters.activity_tags == (ActivityTag.DEVOPS,)


def test_parse_team_plan_response_supports_headcount_greater_than_one() -> None:
    raw = """
    {
      "team_slots": [
        {
          "slot_id": 1,
          "role_label": "Backend Developer",
          "headcount": 2,
          "filters": {
            "department": null,
            "designation": null,
            "skill_category": "BACKEND",
            "skill_name": "Java",
            "min_proficiency": "INTERMEDIATE",
            "min_free_hours_per_week": null,
            "activity_tags": [],
            "work_status": "BENCH"
          }
        }
      ]
    }
    """

    plan = parse_team_plan_response(raw)

    slot = plan.team_slots[0]
    assert slot.headcount == 2
    assert slot.filters.work_status == ResourceWorkStatus.BENCH


def test_parse_team_plan_response_ignores_invalid_enum_values() -> None:
    raw = """
    {
      "team_slots": [
        {
          "slot_id": 1,
          "role_label": "QA Tester",
          "headcount": 1,
          "filters": {
            "department": "Engineering",
            "designation": null,
            "skill_category": "NOT_A_CATEGORY",
            "skill_name": "Manual Testing",
            "min_proficiency": "ADVANCED",
            "min_free_hours_per_week": null,
            "activity_tags": ["TESTING_QA", "NOT_A_TAG"],
            "work_status": null
          }
        }
      ]
    }
    """

    plan = parse_team_plan_response(raw)

    filters = plan.team_slots[0].filters
    assert filters.department == "Engineering"
    assert filters.skill_category is None
    assert filters.activity_tags == (ActivityTag.TESTING_QA,)


def test_parse_team_plan_response_rejects_empty_team_slots() -> None:
    with pytest.raises(LlmUnavailableError, match="missing team_slots"):
        parse_team_plan_response('{"team_slots": []}')


def test_parse_team_plan_response_rejects_invalid_json() -> None:
    with pytest.raises(LlmUnavailableError, match="invalid team plan"):
        parse_team_plan_response("not-json")
