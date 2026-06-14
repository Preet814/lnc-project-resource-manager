"""Parse LLM responses into domain DTOs."""

import json
import re

from prm.domain.dtos import SkillMatchCandidate, SkillMatchResult
from prm.domain.exceptions import LlmUnavailableError


def extract_json_text(raw_text: str) -> str:
    """Return JSON object text, stripping optional markdown fences."""
    text = raw_text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return text.strip()


def extract_json_object(raw_text: str) -> str:
    """Return a JSON object substring, tolerating leading or trailing LLM prose."""
    text = extract_json_text(raw_text)
    try:
        json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        if start < 0:
            return text
        depth = 0
        for index in range(start, len(text)):
            char = text[index]
            if char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    return text[start : index + 1]
    return text


def parse_skill_match_response(
    raw_text: str,
    candidates: tuple[SkillMatchCandidate, ...],
) -> tuple[SkillMatchResult, ...]:
    allowed_ids = {candidate.user_id for candidate in candidates}
    try:
        payload = json.loads(extract_json_text(raw_text))
    except json.JSONDecodeError as exc:
        raise LlmUnavailableError("LLM returned an invalid skill match response.") from exc

    raw_matches = payload.get("matches")
    if not isinstance(raw_matches, list):
        raise LlmUnavailableError("LLM skill match response missing matches list.")

    results: list[SkillMatchResult] = []
    for item in raw_matches:
        if not isinstance(item, dict):
            continue
        user_id = item.get("user_id")
        if user_id not in allowed_ids:
            continue
        reason = item.get("reason")
        user_name = item.get("user_name")
        suggested_allocation_percent = item.get("suggested_allocation_percent")
        free_hours_per_week = item.get("free_hours_per_week")
        if (
            not isinstance(reason, str)
            or not isinstance(user_name, str)
            or not isinstance(suggested_allocation_percent, int)
            or not isinstance(free_hours_per_week, int)
        ):
            continue
        results.append(
            SkillMatchResult(
                user_id=user_id,
                user_name=user_name,
                reason=reason,
                suggested_allocation_percent=suggested_allocation_percent,
                free_hours_per_week=free_hours_per_week,
            )
        )
    return tuple(results)
