"""Deterministic LLMClient for unit tests."""

from prm.domain.dtos import (
    RiskSummaryContext,
    SkillMatchCandidate,
    SkillMatchContext,
    SkillMatchResult,
)
from prm.domain.exceptions import LlmUnavailableError


class FakeLlmClient:
    """Returns preset responses without calling an external provider."""

    def __init__(
        self,
        *,
        rank_results: tuple[SkillMatchResult, ...] = (),
        risk_summary: str = "Project risks are manageable this week.",
        fail_rank: bool = False,
        fail_risk: bool = False,
    ) -> None:
        self._rank_results = rank_results
        self._risk_summary = risk_summary
        self._fail_rank = fail_rank
        self._fail_risk = fail_risk
        self.rank_calls: list[tuple[SkillMatchContext, tuple[SkillMatchCandidate, ...]]] = []
        self.risk_calls: list[RiskSummaryContext] = []

    def rank_candidates(
        self,
        context: SkillMatchContext,
        candidates: tuple[SkillMatchCandidate, ...],
    ) -> tuple[SkillMatchResult, ...]:
        self.rank_calls.append((context, candidates))
        if self._fail_rank:
            raise LlmUnavailableError("Fake LLM rank failure.")
        if not candidates:
            return ()
        return self._rank_results

    def summarize_risk(self, context: RiskSummaryContext) -> str:
        self.risk_calls.append(context)
        if self._fail_risk:
            raise LlmUnavailableError("Fake LLM risk failure.")
        return self._risk_summary
