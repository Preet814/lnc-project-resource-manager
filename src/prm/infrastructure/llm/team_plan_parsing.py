"""Parse LLM team-plan JSON into domain DTOs."""

import json
from enum import StrEnum
from typing import TypeVar

from prm.domain.dtos import TeamPlan, TeamSlotFilters, TeamSlotSpec
from prm.domain.enums import ActivityTag, ProficiencyLevel, ResourceWorkStatus, SkillCategory
from prm.domain.exceptions import LlmUnavailableError
from prm.infrastructure.llm.parsing import extract_json_text

_EnumT = TypeVar("_EnumT", bound=StrEnum)


def parse_team_plan_response(raw_text: str) -> TeamPlan:
    try:
        payload = json.loads(extract_json_text(raw_text))
    except json.JSONDecodeError as exc:
        raise LlmUnavailableError("LLM returned an invalid team plan response.") from exc

    raw_slots = payload.get("team_slots")
    if not isinstance(raw_slots, list) or not raw_slots:
        raise LlmUnavailableError("LLM team plan response missing team_slots list.")

    slots: list[TeamSlotSpec] = []
    for item in raw_slots:
        parsed = _parse_slot(item)
        if parsed is not None:
            slots.append(parsed)

    if not slots:
        raise LlmUnavailableError("LLM returned no usable team slots.")
    return TeamPlan(team_slots=tuple(slots))


def _parse_slot(item: object) -> TeamSlotSpec | None:
    if not isinstance(item, dict):
        return None

    slot_id = item.get("slot_id")
    role_label = item.get("role_label")
    headcount = item.get("headcount")
    raw_filters = item.get("filters")

    if not isinstance(slot_id, int) or slot_id <= 0:
        return None
    if not isinstance(role_label, str) or not role_label.strip():
        return None
    if not isinstance(headcount, int) or headcount <= 0:
        return None

    filters = _parse_filters(raw_filters)
    if filters is None:
        return None

    return TeamSlotSpec(
        slot_id=slot_id,
        role_label=role_label.strip(),
        headcount=headcount,
        filters=filters,
    )


def _parse_filters(raw_filters: object) -> TeamSlotFilters | None:
    if not isinstance(raw_filters, dict):
        return None

    department = _optional_non_empty_str(raw_filters.get("department"))
    designation = _optional_non_empty_str(raw_filters.get("designation"))
    skill_name = _optional_non_empty_str(raw_filters.get("skill_name"))
    skill_category = _optional_enum(raw_filters.get("skill_category"), SkillCategory)
    min_proficiency = _optional_enum(raw_filters.get("min_proficiency"), ProficiencyLevel)
    work_status = _optional_enum(raw_filters.get("work_status"), ResourceWorkStatus)
    min_free_hours = _optional_positive_int(raw_filters.get("min_free_hours_per_week"))
    activity_tags = _parse_activity_tags(raw_filters.get("activity_tags"))

    return TeamSlotFilters(
        department=department,
        designation=designation,
        skill_category=skill_category,
        skill_name=skill_name,
        min_proficiency=min_proficiency,
        min_free_hours_per_week=min_free_hours,
        activity_tags=activity_tags,
        work_status=work_status,
    )


def _optional_non_empty_str(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None


def _optional_enum(value: object, enum_type: type[_EnumT]) -> _EnumT | None:
    if value is None:
        return None
    if not isinstance(value, str):
        return None
    try:
        return enum_type(value)
    except ValueError:
        return None


def _optional_positive_int(value: object) -> int | None:
    if value is None:
        return None
    if not isinstance(value, int) or value <= 0:
        return None
    return value


def _parse_activity_tags(value: object) -> tuple[ActivityTag, ...]:
    if not isinstance(value, list):
        return ()
    tags: list[ActivityTag] = []
    for item in value:
        if not isinstance(item, str):
            continue
        try:
            tags.append(ActivityTag(item))
        except ValueError:
            continue
    return tuple(tags)
