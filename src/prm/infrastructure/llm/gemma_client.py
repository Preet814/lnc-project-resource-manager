"""Self-hosted Gemma adapter (Ollama-compatible /api/generate API)."""

import httpx

from prm.domain.dtos import (
    RiskSummaryContext,
    SkillMatchCandidate,
    SkillMatchContext,
    SkillMatchResult,
    TeamPlan,
    TeamPlanParseContext,
)
from prm.domain.enums import LLMProvider
from prm.domain.exceptions import LlmUnavailableError
from prm.infrastructure.llm.parsing import parse_skill_match_response
from prm.infrastructure.llm.prompts import (
    build_risk_summary_prompt,
    build_skill_match_prompt,
    build_team_plan_prompt,
)
from prm.infrastructure.llm.team_plan_parsing import parse_team_plan_response
from prm.infrastructure.llm.validation import validate_llm_base_url, validate_llm_model


class GemmaClient:
    """Adapter for Ollama-style POST /api/generate endpoints."""

    def __init__(
        self,
        api_key: str,
        *,
        base_url: str,
        model: str,
        http_client: httpx.Client | None = None,
    ) -> None:
        self._api_key = api_key
        self._base_url = validate_llm_base_url(LLMProvider.GEMMA, base_url)
        self._model = validate_llm_model(model)
        self._http = http_client or httpx.Client(timeout=120.0)
        self._owns_client = http_client is None

    def rank_candidates(
        self,
        context: SkillMatchContext,
        candidates: tuple[SkillMatchCandidate, ...],
    ) -> tuple[SkillMatchResult, ...]:
        if not candidates:
            return ()
        prompt = build_skill_match_prompt(context, candidates)
        raw_text = self._generate_text(prompt)
        results = parse_skill_match_response(raw_text, candidates)
        if not results:
            raise LlmUnavailableError("LLM returned no usable skill match results.")
        return results

    def summarize_risk(self, context: RiskSummaryContext) -> str:
        prompt = build_risk_summary_prompt(context)
        summary = self._generate_text(prompt).strip()
        if not summary:
            raise LlmUnavailableError("LLM returned an empty risk summary.")
        return summary

    def parse_team_plan(self, context: TeamPlanParseContext) -> TeamPlan:
        prompt = build_team_plan_prompt(context)
        raw_text = self._generate_text(prompt)
        return parse_team_plan_response(raw_text)

    def _generate_text(self, prompt: str) -> str:
        body: dict[str, object] = {
            "model": self._model,
            "prompt": prompt,
            "stream": False,
        }
        headers = {
            "apikey": self._api_key,
            "Content-Type": "application/json",
        }

        try:
            response = self._http.post(
                f"{self._base_url}/api/generate",
                headers=headers,
                json=body,
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise LlmUnavailableError("Gemma request failed.") from exc

        try:
            payload = response.json()
            text = payload["response"]
        except (KeyError, TypeError) as exc:
            raise LlmUnavailableError("Gemma response format was unexpected.") from exc

        if not isinstance(text, str):
            raise LlmUnavailableError("Gemma response format was unexpected.")
        return text

    def close(self) -> None:
        if self._owns_client:
            self._http.close()
