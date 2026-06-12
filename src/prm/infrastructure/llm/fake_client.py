"""Deterministic LLMClient for unit tests."""

from prm.domain.dtos import (
    RiskSummaryContext,
    SkillMatchCandidate,
    SkillMatchContext,
    SkillMatchResult,
    TeamPlan,
    TeamPlanParseContext,
)
from prm.domain.exceptions import LlmUnavailableError


class FakeLlmClient:
    """Returns preset responses without calling an external provider."""

    def __init__(
        self,
        *,
        rank_results: tuple[SkillMatchResult, ...] = (),
        risk_summary: str = "Project risks are manageable this week.",
        team_plan: TeamPlan | None = None,
        fail_rank: bool = False,
        fail_risk: bool = False,
        fail_parse_team_plan: bool = False,
    ) -> None:
        self._rank_results = rank_results
        self._risk_summary = risk_summary
        self._team_plan = team_plan
        self._fail_rank = fail_rank
        self._fail_risk = fail_risk
        self._fail_parse_team_plan = fail_parse_team_plan
        self.rank_calls: list[tuple[SkillMatchContext, tuple[SkillMatchCandidate, ...]]] = []
        self.risk_calls: list[RiskSummaryContext] = []
        self.parse_team_plan_calls: list[TeamPlanParseContext] = []

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

    def parse_team_plan(self, context: TeamPlanParseContext) -> TeamPlan:
        self.parse_team_plan_calls.append(context)
        if self._fail_parse_team_plan:
            raise LlmUnavailableError("Fake LLM team plan parse failure.")
        if self._team_plan is None:
            raise LlmUnavailableError("Fake LLM has no preset team plan.")
        return self._team_plan
