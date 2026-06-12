"""Multi-role team builder with deterministic assignment and gap analysis."""

from datetime import date

from prm.application.authorization_service import AuthorizationService
from prm.application.protocols import (
    AllocationRepository,
    ProjectRepository,
    SkillRepository,
    UserRepository,
    UserSkillRepository,
)
from prm.domain.constants import MAX_UTILISATION_PERCENT
from prm.domain.dtos import (
    TeamAvailabilityHint,
    TeamBuilderAllocationFact,
    TeamBuilderCandidate,
    TeamBuilderResult,
    TeamBuilderSkill,
    TeamRoleAssignment,
    TeamRoleGap,
    TeamRoleRequirement,
    TeamRoleSkillRequirement,
)
from prm.domain.enums import ProficiencyLevel, TeamGapType
from prm.domain.exceptions import ValidationError

_PROFICIENCY_ORDER: dict[ProficiencyLevel, int] = {
    ProficiencyLevel.BEGINNER: 0,
    ProficiencyLevel.INTERMEDIATE: 1,
    ProficiencyLevel.ADVANCED: 2,
}


class TeamBuilderService:
    """Build a whole project team in one pass without double-booking anyone."""

    def __init__(
        self,
        user_repository: UserRepository,
        user_skill_repository: UserSkillRepository,
        skill_repository: SkillRepository,
        allocation_repository: AllocationRepository,
        project_repository: ProjectRepository,
        authorization: AuthorizationService,
        *,
        max_weekly_hours: int,
    ) -> None:
        self._users = user_repository
        self._user_skills = user_skill_repository
        self._skills = skill_repository
        self._allocations = allocation_repository
        self._projects = project_repository
        self._authorization = authorization
        self._max_weekly_hours = max_weekly_hours

    def build_team(
        self,
        manager_user_id: int,
        project_id: int,
        roles: tuple[TeamRoleRequirement, ...],
        *,
        as_of: date | None = None,
    ) -> TeamBuilderResult:
        project = self._authorization.assert_project_owner(manager_user_id, project_id)
        if not project.allows_allocation():
            raise ValidationError(
                "Project must be ACTIVE or PLANNED to accept allocations."
            )

        cleaned_roles = self._validate_roles(roles)
        reference = as_of or date.today()
        candidates = self._load_candidates(manager_user_id, project_id, reference)
        return self._assign_roles(project_id, cleaned_roles, candidates)

    def _validate_roles(
        self,
        roles: tuple[TeamRoleRequirement, ...],
    ) -> tuple[TeamRoleRequirement, ...]:
        if not roles:
            raise ValidationError("At least one role is required.")

        cleaned: list[TeamRoleRequirement] = []
        for role in roles:
            label = role.role_label.strip()
            if not label:
                raise ValidationError("Each role must have a label.")
            if not role.required_skills:
                raise ValidationError(f"Role '{label}' must include at least one skill.")
            if role.hours_per_week is not None and role.hours_per_week <= 0:
                raise ValidationError(
                    f"Role '{label}' hours per week must be greater than zero."
                )
            skill_requirements = tuple(
                TeamRoleSkillRequirement(
                    skill_name=req.skill_name.strip(),
                    min_proficiency=req.min_proficiency,
                )
                for req in role.required_skills
            )
            if any(not req.skill_name for req in skill_requirements):
                raise ValidationError(f"Role '{label}' has an empty skill name.")
            cleaned.append(
                TeamRoleRequirement(
                    role_label=label,
                    required_skills=skill_requirements,
                    hours_per_week=role.hours_per_week,
                )
            )
        return tuple(cleaned)

    def _load_candidates(
        self,
        manager_user_id: int,
        project_id: int,
        as_of: date,
    ) -> tuple[TeamBuilderCandidate, ...]:
        loaded: list[TeamBuilderCandidate] = []
        for engineer in self._users.list_by_manager_id(
            manager_user_id,
            active_only=True,
        ):
            utilisation = engineer.utilisation_percent or 0
            free_hours = self._free_hours_per_week(utilisation)
            other_allocations = self._other_allocations(engineer.id, project_id)
            loaded.append(
                TeamBuilderCandidate(
                    user_id=engineer.id,
                    full_name=engineer.full_name,
                    skills=self._skills_for_user(engineer.id),
                    utilisation_percent=utilisation,
                    free_hours_per_week=free_hours,
                    other_allocations=other_allocations,
                )
            )
        _ = as_of
        return tuple(loaded)

    def _other_allocations(
        self,
        user_id: int,
        exclude_project_id: int,
    ) -> tuple[TeamBuilderAllocationFact, ...]:
        facts: list[TeamBuilderAllocationFact] = []
        for allocation in self._allocations.find_active_by_user(user_id):
            if allocation.project_id == exclude_project_id:
                continue
            project = self._projects.find_by_id(allocation.project_id)
            project_name = project.name if project is not None else "Unknown project"
            facts.append(
                TeamBuilderAllocationFact(
                    project_name=project_name,
                    utilisation_percent=allocation.utilisation_percent,
                    to_date=allocation.to_date,
                )
            )
        return tuple(facts)

    def _skills_for_user(self, user_id: int) -> tuple[TeamBuilderSkill, ...]:
        skills: list[TeamBuilderSkill] = []
        for assignment in self._user_skills.list_for_user(user_id):
            skill = self._skills.find_by_id(assignment.skill_id)
            if skill is not None:
                skills.append(
                    TeamBuilderSkill(name=skill.name, proficiency=assignment.proficiency)
                )
        return tuple(skills)

    def _assign_roles(
        self,
        project_id: int,
        roles: tuple[TeamRoleRequirement, ...],
        candidates: tuple[TeamBuilderCandidate, ...],
    ) -> TeamBuilderResult:
        assigned_user_ids: set[int] = set()
        assignments: list[TeamRoleAssignment] = []
        gaps: list[TeamRoleGap] = []

        role_order = sorted(
            roles,
            key=lambda role: len(self._eligible_candidates(role, candidates, assigned_user_ids)),
        )

        for role in role_order:
            eligible = self._eligible_candidates(role, candidates, assigned_user_ids)
            if eligible:
                best = max(eligible, key=lambda candidate: self._score_candidate(role, candidate))
                suggested_percent = self._suggested_allocation_percent(role, best)
                assignments.append(
                    TeamRoleAssignment(
                        role_label=role.role_label,
                        user_id=best.user_id,
                        user_name=best.full_name,
                        suggested_allocation_percent=suggested_percent,
                        reason=self._assignment_reason(role, best),
                        free_hours_per_week=best.free_hours_per_week,
                    )
                )
                assigned_user_ids.add(best.user_id)
                continue

            gap = self._build_gap(role, candidates, assigned_user_ids)
            gaps.append(gap)

        assignment_by_role = {item.role_label: item for item in assignments}
        ordered_assignments = tuple(
            assignment_by_role[role.role_label]
            for role in roles
            if role.role_label in assignment_by_role
        )
        gap_by_role = {item.role_label: item for item in gaps}
        ordered_gaps = tuple(
            gap_by_role[role.role_label] for role in roles if role.role_label in gap_by_role
        )
        return TeamBuilderResult(
            project_id=project_id,
            assignments=ordered_assignments,
            gaps=ordered_gaps,
        )

    def _eligible_candidates(
        self,
        role: TeamRoleRequirement,
        candidates: tuple[TeamBuilderCandidate, ...],
        assigned_user_ids: set[int],
    ) -> list[TeamBuilderCandidate]:
        eligible: list[TeamBuilderCandidate] = []
        for candidate in candidates:
            if candidate.user_id in assigned_user_ids:
                continue
            if not self._has_required_skills(candidate, role.required_skills):
                continue
            if not self._has_capacity(candidate, role.hours_per_week):
                continue
            eligible.append(candidate)
        return eligible

    def _skill_qualified_candidates(
        self,
        role: TeamRoleRequirement,
        candidates: tuple[TeamBuilderCandidate, ...],
    ) -> list[TeamBuilderCandidate]:
        return [
            candidate
            for candidate in candidates
            if self._has_required_skills(candidate, role.required_skills)
        ]

    def _build_gap(
        self,
        role: TeamRoleRequirement,
        candidates: tuple[TeamBuilderCandidate, ...],
        assigned_user_ids: set[int],
    ) -> TeamRoleGap:
        skill_qualified = self._skill_qualified_candidates(role, candidates)
        if not skill_qualified:
            return TeamRoleGap(
                role_label=role.role_label,
                gap_type=TeamGapType.SKILL_GAP,
                detail=self._skill_gap_detail(role),
            )

        blocked_by_team_plan = [
            candidate
            for candidate in skill_qualified
            if candidate.user_id in assigned_user_ids
            and self._has_capacity(candidate, role.hours_per_week)
        ]
        if blocked_by_team_plan:
            names = ", ".join(candidate.full_name for candidate in blocked_by_team_plan)
            return TeamRoleGap(
                role_label=role.role_label,
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
                    for candidate in blocked_by_team_plan
                ),
            )

        unavailable = [
            candidate
            for candidate in skill_qualified
            if candidate.user_id not in assigned_user_ids
            and not self._has_capacity(candidate, role.hours_per_week)
        ]
        primary = unavailable[0] if unavailable else skill_qualified[0]
        return TeamRoleGap(
            role_label=role.role_label,
            gap_type=TeamGapType.AVAILABILITY_GAP,
            detail=self._availability_gap_detail(role, primary),
            availability_hints=tuple(
                TeamAvailabilityHint(
                    user_name=candidate.full_name,
                    available_from=self._latest_allocation_end(candidate),
                )
                for candidate in unavailable
            ),
        )

    @staticmethod
    def _skill_gap_detail(role: TeamRoleRequirement) -> str:
        parts = [
            f"{req.skill_name} at {req.min_proficiency.value}+"
            for req in role.required_skills
        ]
        skills_text = ", ".join(parts)
        return f"No engineer on your team has {skills_text}. Consider hire or training."

    def _availability_gap_detail(
        self,
        role: TeamRoleRequirement,
        candidate: TeamBuilderCandidate,
    ) -> str:
        needed = role.hours_per_week
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
    def _allocation_summary(candidate: TeamBuilderCandidate) -> str:
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
    def _latest_allocation_end(candidate: TeamBuilderCandidate) -> date | None:
        ends = [fact.to_date for fact in candidate.other_allocations if fact.to_date is not None]
        if not ends:
            return None
        return max(ends)

    def _score_candidate(
        self,
        role: TeamRoleRequirement,
        candidate: TeamBuilderCandidate,
    ) -> tuple[int, int, int]:
        proficiency_bonus = sum(
            self._proficiency_headroom(candidate, requirement)
            for requirement in role.required_skills
        )
        bench_bonus = MAX_UTILISATION_PERCENT - candidate.utilisation_percent
        return (candidate.free_hours_per_week, proficiency_bonus, bench_bonus)

    def _proficiency_headroom(
        self,
        candidate: TeamBuilderCandidate,
        requirement: TeamRoleSkillRequirement,
    ) -> int:
        actual = self._skill_proficiency(candidate, requirement.skill_name)
        if actual is None:
            return 0
        return _PROFICIENCY_ORDER[actual] - _PROFICIENCY_ORDER[requirement.min_proficiency]

    def _suggested_allocation_percent(
        self,
        role: TeamRoleRequirement,
        candidate: TeamBuilderCandidate,
    ) -> int:
        if role.hours_per_week is not None:
            needed_percent = (
                role.hours_per_week * MAX_UTILISATION_PERCENT
            ) // self._max_weekly_hours
            remaining = MAX_UTILISATION_PERCENT - candidate.utilisation_percent
            return min(remaining, max(1, needed_percent))
        if candidate.free_hours_per_week >= self._max_weekly_hours:
            return 50
        needed_percent = (
            candidate.free_hours_per_week * MAX_UTILISATION_PERCENT
        ) // self._max_weekly_hours
        return max(1, min(needed_percent, MAX_UTILISATION_PERCENT - candidate.utilisation_percent))

    @staticmethod
    def _assignment_reason(
        role: TeamRoleRequirement,
        candidate: TeamBuilderCandidate,
    ) -> str:
        skill_names = ", ".join(req.skill_name for req in role.required_skills)
        return (
            f"{candidate.full_name} matches {role.role_label} with required skills "
            f"({skill_names}) and {candidate.free_hours_per_week} free hrs/week."
        )

    def _has_required_skills(
        self,
        candidate: TeamBuilderCandidate,
        requirements: tuple[TeamRoleSkillRequirement, ...],
    ) -> bool:
        return all(
            self._meets_proficiency(candidate, requirement)
            for requirement in requirements
        )

    def _meets_proficiency(
        self,
        candidate: TeamBuilderCandidate,
        requirement: TeamRoleSkillRequirement,
    ) -> bool:
        actual = self._skill_proficiency(candidate, requirement.skill_name)
        if actual is None:
            return False
        return _PROFICIENCY_ORDER[actual] >= _PROFICIENCY_ORDER[requirement.min_proficiency]

    @staticmethod
    def _skill_proficiency(
        candidate: TeamBuilderCandidate,
        skill_name: str,
    ) -> ProficiencyLevel | None:
        normalized = skill_name.casefold()
        for skill in candidate.skills:
            if skill.name.casefold() == normalized:
                return skill.proficiency
        return None

    def _has_capacity(
        self,
        candidate: TeamBuilderCandidate,
        hours_per_week: int | None,
    ) -> bool:
        if hours_per_week is not None:
            return candidate.free_hours_per_week >= hours_per_week
        return candidate.free_hours_per_week > 0

    def _free_hours_per_week(self, utilisation_percent: int) -> int:
        availability_percent = max(0, MAX_UTILISATION_PERCENT - utilisation_percent)
        return (availability_percent * self._max_weekly_hours) // MAX_UTILISATION_PERCENT
