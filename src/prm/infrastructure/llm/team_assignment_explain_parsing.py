"""Parse LLM team assignment explain responses."""

import json

from prm.domain.dtos import TeamAssignmentExplainContext, TeamAssignmentReason
from prm.domain.exceptions import LlmUnavailableError
from prm.infrastructure.llm.parsing import extract_json_text


def parse_team_assignment_explain_response(
    raw_text: str,
    context: TeamAssignmentExplainContext,
) -> tuple[TeamAssignmentReason, ...]:
    allowed_keys = {
        (slot.slot_id, slot.position, slot.user_id) for slot in context.slots
    }
    try:
        payload = json.loads(extract_json_text(raw_text))
    except json.JSONDecodeError as exc:
        raise LlmUnavailableError(
            "LLM returned an invalid team assignment explain response."
        ) from exc

    raw_reasons = payload.get("reasons")
    if not isinstance(raw_reasons, list):
        raise LlmUnavailableError(
            "LLM team assignment explain response missing reasons list."
        )

    results: list[TeamAssignmentReason] = []
    for item in raw_reasons:
        if not isinstance(item, dict):
            continue
        slot_id = item.get("slot_id")
        position = item.get("position")
        user_id = item.get("user_id")
        reason = item.get("reason")
        if (
            not isinstance(slot_id, int)
            or not isinstance(position, int)
            or not isinstance(user_id, int)
            or not isinstance(reason, str)
            or not reason.strip()
        ):
            continue
        key = (slot_id, position, user_id)
        if key not in allowed_keys:
            continue
        results.append(
            TeamAssignmentReason(
                slot_id=slot_id,
                position=position,
                user_id=user_id,
                reason=reason.strip(),
            )
        )
    return tuple(results)
