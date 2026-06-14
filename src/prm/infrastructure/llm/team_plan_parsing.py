"""Parse LLM team-plan JSON into domain DTOs."""

import json
from enum import StrEnum
from typing import TypeVar

from prm.domain.dtos import TeamPlan, TeamSlotFilters, TeamSlotSpec
from prm.domain.enums import ActivityTag, ProficiencyLevel, ResourceWorkStatus, SkillCategory
from prm.domain.exceptions import LlmUnavailableError
from prm.infrastructure.llm.parsing import extract_json_object

_EnumT = TypeVar("_EnumT", bound=StrEnum)


def parse_team_plan_response(raw_text: str) -> TeamPlan:
    json_text = extract_json_object(raw_text)
    try:
        payload = json.loads(json_text)
    except json.JSONDecodeError as exc:
        raise LlmUnavailableError("LLM returned an invalid team plan response.") from exc

    if not isinstance(payload, dict):
        raise LlmUnavailableError("LLM team plan response must be a JSON object.")

    raw_slots = payload.get("team_slots")
    if not isinstance(raw_slots, list) or not raw_slots:
        raise LlmUnavailableError("LLM team plan response missing team_slots list.")

    slots: list[TeamSlotSpec] = []
    for item in raw_slots:
        parsed = _parse_slot(item)
        if parsed is not None:
            slots.append(parsed)

    if not slots:
        raise LlmUnavailableError(
            "LLM returned no usable team slots. Check slot_id, headcount, and filters shape."
        )
    return TeamPlan(team_slots=tuple(slots))


def _parse_slot(item: object) -> TeamSlotSpec | None:
    if not isinstance(item, dict):
        return None

    slot_id = _coerce_positive_int(item.get("slot_id"))
    role_label = item.get("role_label")
    headcount = _coerce_positive_int(item.get("headcount"))

    if slot_id is None:
        return None
    if not isinstance(role_label, str) or not role_label.strip():
        return None
    if headcount is None:
        headcount = 1

    return TeamSlotSpec(
        slot_id=slot_id,
        role_label=role_label.strip(),
        headcount=headcount,
        filters=_parse_filters(item.get("filters")),
    )


def _parse_filters(raw_filters: object) -> TeamSlotFilters:
    if not isinstance(raw_filters, dict):
        return TeamSlotFilters()

    return TeamSlotFilters(
        department=_optional_non_empty_str(raw_filters.get("department")),
        designation=_optional_non_empty_str(raw_filters.get("designation")),
        skill_category=_optional_enum(raw_filters.get("skill_category"), SkillCategory),
        skill_name=_optional_non_empty_str(raw_filters.get("skill_name")),
        min_proficiency=_optional_enum(raw_filters.get("min_proficiency"), ProficiencyLevel),
        min_free_hours_per_week=_coerce_positive_int(
            raw_filters.get("min_free_hours_per_week")
        ),
        activity_tags=_parse_activity_tags(raw_filters.get("activity_tags")),
        work_status=_optional_enum(raw_filters.get("work_status"), ResourceWorkStatus),
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


def _coerce_positive_int(value: object) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value > 0 else None
    if isinstance(value, float) and value.is_integer():
        coerced = int(value)
        return coerced if coerced > 0 else None
    if isinstance(value, str):
        stripped = value.strip()
        if stripped.isdigit():
            coerced = int(stripped)
            return coerced if coerced > 0 else None
    return None


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
