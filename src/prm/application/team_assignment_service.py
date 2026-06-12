"""Assign a team plan using search filters, scoring, and typed gap reporting."""

from datetime import date

from prm.application.authorization_service import AuthorizationService
from prm.application.team_candidate_search_service import TeamCandidateSearchService
from prm.domain.constants import MAX_UTILISATION_PERCENT
from prm.domain.dtos import (
    TeamAssignmentResult,
    TeamAvailabilityHint,
    TeamPlan,
    TeamSearchCandidate,
    TeamSlotAssignment,
    TeamSlotFilters,
    TeamSlotGap,
    TeamSlotSpec,
)
from prm.domain.enums import ProficiencyLevel, ResourceWorkStatus, TeamGapType
from prm.domain.exceptions import ValidationError

_PROFICIENCY_ORDER: dict[ProficiencyLevel, int] = {
    ProficiencyLevel.BEGINNER: 0,
    ProficiencyLevel.INTERMEDIATE: 1,
    ProficiencyLevel.ADVANCED: 2,
}


class TeamAssignmentService:
    """Pick unique engineers per slot using code-only search and scoring."""

    def __init__(
        self,
        search_service: TeamCandidateSearchService,
        authorization: AuthorizationService,
        *,
        max_weekly_hours: int,
    ) -> None:
        self._search = search_service
        self._authorization = authorization
        self._max_weekly_hours = max_weekly_hours

    def assign_team(
        self,
        manager_user_id: int,
        project_id: int,
        plan: TeamPlan,
        *,
        requirement: str | None = None,
        as_of: date | None = None,
    ) -> TeamAssignmentResult:
        project = self._authorization.assert_project_owner(manager_user_id, project_id)
        if not project.allows_allocation():
            raise ValidationError(
                "Project must be ACTIVE or PLANNED to accept allocations."
            )
        if not plan.team_slots:
            raise ValidationError("Team plan must include at least one slot.")

        assigned_user_ids: set[int] = set()
        assignments: list[TeamSlotAssignment] = []
        gaps: list[TeamSlotGap] = []

        slot_order = sorted(
            plan.team_slots,
            key=lambda slot: len(
                self._search.search_candidates(
                    manager_user_id,
                    slot.filters,
                    exclude_user_ids=assigned_user_ids,
                    exclude_project_id=project_id,
                    as_of=as_of,
                )
            ),
        )

        for slot in slot_order:
            for position in range(1, slot.headcount + 1):
                eligible = self._search.search_candidates(
                    manager_user_id,
                    slot.filters,
                    exclude_user_ids=assigned_user_ids,
                    exclude_project_id=project_id,
                    as_of=as_of,
                )
                if eligible:
                    best = max(
                        eligible,
                        key=lambda candidate: self._score_candidate(
                            slot.filters,
                            candidate,
                        ),
                    )
                    suggested_percent = self._suggested_allocation_percent(
                        slot.filters,
                        best,
                    )
                    assignments.append(
                        TeamSlotAssignment(
                            slot_id=slot.slot_id,
                            role_label=slot.role_label,
                            position=position,
                            user_id=best.user_id,
                            user_name=best.full_name,
                            suggested_allocation_percent=suggested_percent,
                            reason=self._assignment_reason(slot, best),
                            free_hours_per_week=best.free_hours_per_week,
                        )
                    )
                    assigned_user_ids.add(best.user_id)
                    continue

                gaps.append(
                    self._build_gap(
                        manager_user_id,
                        project_id,
                        slot,
                        position,
                        assigned_user_ids,
                        as_of=as_of,
                    )
                )

        return TeamAssignmentResult(
            project_id=project_id,
            requirement=requirement,
            assignments=self._order_assignments(plan, assignments),
            gaps=self._order_gaps(plan, gaps),
        )

    def _build_gap(
        self,
        manager_user_id: int,
        project_id: int,
        slot: TeamSlotSpec,
        position: int,
        assigned_user_ids: set[int],
        *,
        as_of: date | None,
    ) -> TeamSlotGap:
        skill_pool = self._search.search_candidates(
            manager_user_id,
            self._without_capacity_filters(slot.filters),
            exclude_project_id=project_id,
            as_of=as_of,
        )
        if not skill_pool:
            return TeamSlotGap(
                slot_id=slot.slot_id,
                role_label=slot.role_label,
                position=position,
                gap_type=TeamGapType.SKILL_GAP,
                detail=self._skill_gap_detail(slot),
            )

        blocked = [
            candidate
            for candidate in skill_pool
            if candidate.user_id in assigned_user_ids
            and self._has_capacity(candidate, slot.filters)
        ]
        if blocked:
            names = ", ".join(candidate.full_name for candidate in blocked)
            return TeamSlotGap(
                slot_id=slot.slot_id,
                role_label=slot.role_label,
                position=position,
                gap_type=TeamGapType.AVAILABILITY_GAP,
                detail=(
                    f"Qualified engineers exist but are already assigned to other roles "
                    f"in this team plan: {names}."
                ),
                availability_hints=tuple(
                    TeamAvailabilityHint(
                        user_name=candidate.full_name,
                        available_from=self._latest_allocation_end(candidate),
                    )
                    for candidate in blocked
                ),
            )

        unavailable = [
            candidate
            for candidate in skill_pool
            if candidate.user_id not in assigned_user_ids
            and not self._has_capacity(candidate, slot.filters)
        ]
        primary = unavailable[0] if unavailable else skill_pool[0]
        return TeamSlotGap(
            slot_id=slot.slot_id,
            role_label=slot.role_label,
            position=position,
            gap_type=TeamGapType.AVAILABILITY_GAP,
            detail=self._availability_gap_detail(slot, primary),
            availability_hints=tuple(
                TeamAvailabilityHint(
                    user_name=candidate.full_name,
                    available_from=self._latest_allocation_end(candidate),
                )
                for candidate in unavailable
            ),
        )

    def _score_candidate(
        self,
        filters: TeamSlotFilters,
        candidate: TeamSearchCandidate,
    ) -> tuple[int, int, int, int]:
        bench_bonus = (
            1
            if filters.work_status is None
            and candidate.work_status == ResourceWorkStatus.BENCH
            else 0
        )
        proficiency_bonus = self._proficiency_headroom(filters, candidate)
        activity_bonus = self._activity_overlap_bonus(filters, candidate)
        return (
            candidate.free_hours_per_week,
            bench_bonus,
            proficiency_bonus + activity_bonus,
            MAX_UTILISATION_PERCENT - candidate.utilisation_percent,
        )

    def _proficiency_headroom(
        self,
        filters: TeamSlotFilters,
        candidate: TeamSearchCandidate,
    ) -> int:
        if filters.min_proficiency is None:
            return 0
        for skill in candidate.skills:
            if filters.skill_name is not None:
                if skill.name.casefold() != filters.skill_name.casefold():
                    continue
            if filters.skill_category is not None and skill.category != filters.skill_category:
                continue
            return (
                _PROFICIENCY_ORDER[skill.proficiency]
                - _PROFICIENCY_ORDER[filters.min_proficiency]
            )
        return 0

    @staticmethod
    def _activity_overlap_bonus(
        filters: TeamSlotFilters,
        candidate: TeamSearchCandidate,
    ) -> int:
        if not filters.activity_tags:
            return 0
        candidate_tags = {tag.casefold() for tag in candidate.recent_activity_tags}
        overlap = sum(
            1 for tag in filters.activity_tags if tag.value.casefold() in candidate_tags
        )
        return overlap

    def _suggested_allocation_percent(
        self,
        filters: TeamSlotFilters,
        candidate: TeamSearchCandidate,
    ) -> int:
        remaining = MAX_UTILISATION_PERCENT - candidate.utilisation_percent
        if filters.min_free_hours_per_week is not None:
            needed_percent = (
                filters.min_free_hours_per_week * MAX_UTILISATION_PERCENT
            ) // self._max_weekly_hours
            return min(remaining, max(1, needed_percent))
        if candidate.free_hours_per_week >= self._max_weekly_hours:
            return min(remaining, 50)
        needed_percent = (
            candidate.free_hours_per_week * MAX_UTILISATION_PERCENT
        ) // self._max_weekly_hours
        return max(1, min(needed_percent, remaining))

    @staticmethod
    def _assignment_reason(slot: TeamSlotSpec, candidate: TeamSearchCandidate) -> str:
        return (
            f"{candidate.full_name} matches {slot.role_label} with "
            f"{candidate.free_hours_per_week} free hrs/week."
        )

    @staticmethod
    def _skill_gap_detail(slot: TeamSlotSpec) -> str:
        parts: list[str] = []
        if slot.filters.skill_name is not None:
            proficiency = (
                f" at {slot.filters.min_proficiency.value}+"
                if slot.filters.min_proficiency is not None
                else ""
            )
            parts.append(f"{slot.filters.skill_name}{proficiency}")
        if slot.filters.skill_category is not None:
            parts.append(f"{slot.filters.skill_category.value} skills")
        if slot.filters.department is not None:
            parts.append(f"department {slot.filters.department}")
        detail = ", ".join(parts) if parts else "the required criteria"
        return f"No engineer on your team matches {detail}. Consider hire or training."

    def _availability_gap_detail(
        self,
        slot: TeamSlotSpec,
        candidate: TeamSearchCandidate,
    ) -> str:
        needed = slot.filters.min_free_hours_per_week
        if needed is not None:
            capacity_part = (
                f"only {candidate.free_hours_per_week} free hrs/week "
                f"(need at least {needed})"
            )
        else:
            capacity_part = "has no available capacity"

        allocation_part = self._allocation_summary(candidate)
        if allocation_part:
            return (
                f"{candidate.full_name} has the required skills but {capacity_part}. "
                f"{allocation_part}"
            )
        return f"{candidate.full_name} has the required skills but {capacity_part}."

    @staticmethod
    def _allocation_summary(candidate: TeamSearchCandidate) -> str:
        if not candidate.other_allocations:
            return ""
        allocation = candidate.other_allocations[0]
        until = (
            allocation.to_date.isoformat()
            if allocation.to_date is not None
            else "open-ended"
        )
        return (
            f"Allocated {allocation.utilisation_percent}% on "
            f"{allocation.project_name} until {until}."
        )

    @staticmethod
    def _latest_allocation_end(candidate: TeamSearchCandidate) -> date | None:
        ends = [
            fact.to_date for fact in candidate.other_allocations if fact.to_date is not None
        ]
        if not ends:
            return None
        return max(ends)

    @staticmethod
    def _has_capacity(
        candidate: TeamSearchCandidate,
        filters: TeamSlotFilters,
    ) -> bool:
        if filters.min_free_hours_per_week is not None:
            return candidate.free_hours_per_week >= filters.min_free_hours_per_week
        return candidate.free_hours_per_week > 0

    @staticmethod
    def _without_capacity_filters(filters: TeamSlotFilters) -> TeamSlotFilters:
        return TeamSlotFilters(
            department=filters.department,
            designation=filters.designation,
            skill_category=filters.skill_category,
            skill_name=filters.skill_name,
            min_proficiency=filters.min_proficiency,
            min_free_hours_per_week=None,
            activity_tags=filters.activity_tags,
            work_status=filters.work_status,
        )

    @staticmethod
    def _order_assignments(
        plan: TeamPlan,
        assignments: list[TeamSlotAssignment],
    ) -> tuple[TeamSlotAssignment, ...]:
        by_key = {(item.slot_id, item.position): item for item in assignments}
        ordered: list[TeamSlotAssignment] = []
        for slot in plan.team_slots:
            for position in range(1, slot.headcount + 1):
                key = (slot.slot_id, position)
                if key in by_key:
                    ordered.append(by_key[key])
        return tuple(ordered)

    @staticmethod
    def _order_gaps(plan: TeamPlan, gaps: list[TeamSlotGap]) -> tuple[TeamSlotGap, ...]:
        by_key = {(item.slot_id, item.position): item for item in gaps}
        ordered: list[TeamSlotGap] = []
        for slot in plan.team_slots:
            for position in range(1, slot.headcount + 1):
                key = (slot.slot_id, position)
                if key in by_key:
                    ordered.append(by_key[key])
        return tuple(ordered)
