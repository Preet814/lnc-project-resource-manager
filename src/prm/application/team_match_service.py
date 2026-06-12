"""Orchestrate LLM team-plan parsing and deterministic team assignment."""

from datetime import date

from prm.application.authorization_service import AuthorizationService
from prm.application.protocols import LLMClient
from prm.application.team_assignment_service import TeamAssignmentService
from prm.application.team_candidate_search_service import TeamCandidateSearchService
from prm.domain.dtos import (
    TeamAssignmentExplainContext,
    TeamAssignmentExplainSlot,
    TeamAssignmentReason,
    TeamAssignmentResult,
    TeamPlan,
    TeamPlanParseContext,
    TeamSearchCandidate,
    TeamSlotAssignment,
    TeamSlotSpec,
)
from prm.domain.exceptions import LlmUnavailableError, ValidationError


class TeamMatchService:
    """Parse a plain-English requirement, assign the team, then explain filled slots."""

    def __init__(
        self,
        authorization: AuthorizationService,
        llm_client: LLMClient,
        assignment_service: TeamAssignmentService,
        search_service: TeamCandidateSearchService,
    ) -> None:
        self._authorization = authorization
        self._llm = llm_client
        self._assignment = assignment_service
        self._search = search_service

    def match_team(
        self,
        manager_user_id: int,
        project_id: int,
        requirement: str,
        *,
        as_of: date | None = None,
    ) -> TeamAssignmentResult:
        project = self._authorization.assert_project_owner(manager_user_id, project_id)
        if not project.allows_allocation():
            raise ValidationError(
                "Project must be ACTIVE or PLANNED to accept allocations."
            )

        cleaned = requirement.strip()
        if not cleaned:
            raise ValidationError("Requirement is required.")

        plan = self._llm.parse_team_plan(
            TeamPlanParseContext(
                project_id=project.id,
                project_name=project.name,
                requirement=cleaned,
            )
        )
        result = self._assignment.assign_team(
            manager_user_id,
            project_id,
            plan,
            requirement=cleaned,
            as_of=as_of,
        )
        if not result.assignments:
            return result

        try:
            explain_context = self._build_explain_context(
                project_id=project.id,
                project_name=project.name,
                requirement=cleaned,
                plan=plan,
                result=result,
                manager_user_id=manager_user_id,
                exclude_project_id=project_id,
                as_of=as_of,
            )
            reasons = self._llm.explain_team_assignments(explain_context)
            return self._merge_explain_reasons(result, reasons)
        except LlmUnavailableError:
            return result

    def _build_explain_context(
        self,
        *,
        project_id: int,
        project_name: str,
        requirement: str,
        plan: TeamPlan,
        result: TeamAssignmentResult,
        manager_user_id: int,
        exclude_project_id: int,
        as_of: date | None,
    ) -> TeamAssignmentExplainContext:
        slots_by_id = {slot.slot_id: slot for slot in plan.team_slots}
        explain_slots: list[TeamAssignmentExplainSlot] = []
        for assignment in result.assignments:
            slot = slots_by_id[assignment.slot_id]
            candidate = self._find_assigned_candidate(
                manager_user_id,
                slot,
                assignment.user_id,
                exclude_project_id=exclude_project_id,
                as_of=as_of,
            )
            explain_slots.append(
                self._to_explain_slot(slot, assignment, candidate),
            )
        return TeamAssignmentExplainContext(
            project_id=project_id,
            project_name=project_name,
            requirement=requirement,
            slots=tuple(explain_slots),
        )

    def _find_assigned_candidate(
        self,
        manager_user_id: int,
        slot: TeamSlotSpec,
        user_id: int,
        *,
        exclude_project_id: int,
        as_of: date | None,
    ) -> TeamSearchCandidate | None:
        candidates = self._search.search_candidates(
            manager_user_id,
            slot.filters,
            exclude_project_id=exclude_project_id,
            as_of=as_of,
        )
        return next(
            (candidate for candidate in candidates if candidate.user_id == user_id),
            None,
        )

    @staticmethod
    def _to_explain_slot(
        slot: TeamSlotSpec,
        assignment: TeamSlotAssignment,
        candidate: TeamSearchCandidate | None,
    ) -> TeamAssignmentExplainSlot:
        if candidate is None:
            return TeamAssignmentExplainSlot(
                slot_id=assignment.slot_id,
                position=assignment.position,
                role_label=assignment.role_label,
                filters=slot.filters,
                user_id=assignment.user_id,
                user_name=assignment.user_name,
                suggested_allocation_percent=assignment.suggested_allocation_percent,
                free_hours_per_week=assignment.free_hours_per_week,
                utilisation_percent=0,
                work_status=None,
            )
        return TeamAssignmentExplainSlot(
            slot_id=assignment.slot_id,
            position=assignment.position,
            role_label=assignment.role_label,
            filters=slot.filters,
            user_id=assignment.user_id,
            user_name=assignment.user_name,
            suggested_allocation_percent=assignment.suggested_allocation_percent,
            free_hours_per_week=assignment.free_hours_per_week,
            utilisation_percent=candidate.utilisation_percent,
            work_status=candidate.work_status,
            skills=candidate.skills,
            recent_activity_tags=candidate.recent_activity_tags,
            other_allocations=candidate.other_allocations,
        )

    @staticmethod
    def _merge_explain_reasons(
        result: TeamAssignmentResult,
        reasons: tuple[TeamAssignmentReason, ...],
    ) -> TeamAssignmentResult:
        reason_by_key = {
            (reason.slot_id, reason.position, reason.user_id): reason.reason
            for reason in reasons
        }
        merged_assignments = tuple(
            TeamSlotAssignment(
                slot_id=assignment.slot_id,
                role_label=assignment.role_label,
                position=assignment.position,
                user_id=assignment.user_id,
                user_name=assignment.user_name,
                suggested_allocation_percent=assignment.suggested_allocation_percent,
                reason=reason_by_key.get(
                    (assignment.slot_id, assignment.position, assignment.user_id),
                    assignment.reason,
                ),
                free_hours_per_week=assignment.free_hours_per_week,
            )
            for assignment in result.assignments
        )
        return TeamAssignmentResult(
            project_id=result.project_id,
            assignments=merged_assignments,
            gaps=result.gaps,
            requirement=result.requirement,
        )
