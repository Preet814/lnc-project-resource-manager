"""Groq OpenAI-compatible adapter for LLMClient."""

import httpx

from prm.domain.dtos import (
    RiskSummaryContext,
    SkillMatchCandidate,
    SkillMatchContext,
    SkillMatchResult,
)
from prm.domain.enums import LLMProvider
from prm.domain.exceptions import LlmUnavailableError
from prm.infrastructure.llm.parsing import parse_skill_match_response
from prm.infrastructure.llm.prompts import build_risk_summary_prompt, build_skill_match_prompt
from prm.infrastructure.llm.validation import validate_llm_base_url, validate_llm_model


class GroqClient:
    """Adapter for Groq chat completions API."""

    def __init__(
        self,
        api_key: str,
        *,
        base_url: str,
        model: str,
        http_client: httpx.Client | None = None,
    ) -> None:
        self._api_key = api_key
        self._base_url = validate_llm_base_url(LLMProvider.GROQ, base_url)
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

    def _generate_text(self, prompt: str, *, json_mode: bool) -> str:
        body: dict[str, object] = {
            "model": self._model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.2,
        }
        if json_mode:
            body["response_format"] = {"type": "json_object"}

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

        try:
            response = self._http.post(
                f"{self._base_url}/chat/completions",
                headers=headers,
                json=body,
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise LlmUnavailableError("Groq request failed.") from exc

        try:
            payload = response.json()
            content = payload["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LlmUnavailableError("Groq response format was unexpected.") from exc

        if not isinstance(content, str):
            raise LlmUnavailableError("Groq response format was unexpected.")
        return content

    def close(self) -> None:
        if self._owns_client:
            self._http.close()
