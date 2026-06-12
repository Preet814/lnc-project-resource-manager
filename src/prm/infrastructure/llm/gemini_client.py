"""Google Gemini adapter for LLMClient."""

import httpx

from prm.domain.dtos import (
    RiskSummaryContext,
    SkillMatchCandidate,
    SkillMatchContext,
    SkillMatchResult,
    TeamAssignmentExplainContext,
    TeamAssignmentReason,
    TeamPlan,
    TeamPlanParseContext,
)
from prm.domain.enums import LLMProvider
from prm.domain.exceptions import LlmUnavailableError
from prm.infrastructure.llm.parsing import parse_skill_match_response
from prm.infrastructure.llm.prompts import (
    build_risk_summary_prompt,
    build_skill_match_prompt,
    build_team_assignment_explain_prompt,
    build_team_plan_prompt,
)
from prm.infrastructure.llm.team_assignment_explain_parsing import (
    parse_team_assignment_explain_response,
)
from prm.infrastructure.llm.team_plan_parsing import parse_team_plan_response
from prm.infrastructure.llm.validation import validate_llm_base_url, validate_llm_model


class GeminiClient:
    """Adapter for Gemini generateContent API."""

    def __init__(
        self,
        api_key: str,
        *,
        base_url: str,
        model: str,
        http_client: httpx.Client | None = None,
    ) -> None:
        self._api_key = api_key
        self._base_url = validate_llm_base_url(LLMProvider.GEMINI, base_url)
        self._model = validate_llm_model(model)
        self._http = http_client or httpx.Client(timeout=30.0)
        self._owns_client = http_client is None

    def rank_candidates(
        self,
        context: SkillMatchContext,
        candidates: tuple[SkillMatchCandidate, ...],
    ) -> tuple[SkillMatchResult, ...]:
        if not candidates:
            return ()
        prompt = build_skill_match_prompt(context, candidates)
        raw_text = self._generate_text(prompt, json_mode=True)
        results = parse_skill_match_response(raw_text, candidates)
        if not results:
            raise LlmUnavailableError("LLM returned no usable skill match results.")
        return results

    def summarize_risk(self, context: RiskSummaryContext) -> str:
        prompt = build_risk_summary_prompt(context)
        summary = self._generate_text(prompt, json_mode=False).strip()
        if not summary:
            raise LlmUnavailableError("LLM returned an empty risk summary.")
        return summary

    def parse_team_plan(self, context: TeamPlanParseContext) -> TeamPlan:
        prompt = build_team_plan_prompt(context)
        raw_text = self._generate_text(prompt, json_mode=True)
        return parse_team_plan_response(raw_text)

    def explain_team_assignments(
        self,
        context: TeamAssignmentExplainContext,
    ) -> tuple[TeamAssignmentReason, ...]:
        if not context.slots:
            return ()
        prompt = build_team_assignment_explain_prompt(context)
        raw_text = self._generate_text(prompt, json_mode=True)
        reasons = parse_team_assignment_explain_response(raw_text, context)
        if not reasons:
            raise LlmUnavailableError(
                "LLM returned no usable team assignment explain results."
            )
        return reasons

    def _generate_text(self, prompt: str, *, json_mode: bool) -> str:
        url = f"{self._base_url}/models/{self._model}:generateContent"
        body: dict[str, object] = {
            "contents": [{"parts": [{"text": prompt}]}],
        }
        if json_mode:
            body["generationConfig"] = {"responseMimeType": "application/json"}

        try:
            response = self._http.post(
                url,
                params={"key": self._api_key},
                json=body,
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise LlmUnavailableError("Gemini request failed.") from exc

        try:
            payload = response.json()
            return payload["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LlmUnavailableError("Gemini response format was unexpected.") from exc

    def close(self) -> None:
        if self._owns_client:
            self._http.close()
