"""Search manager-team engineers using optional team-slot filters (code-only, no LLM)."""

from datetime import date

from prm.application.protocols import (
    AllocationRepository,
    ProjectRepository,
    SkillRepository,
    TimesheetRepository,
    UserRepository,
    UserSkillRepository,
)
from prm.domain.constants import MAX_UTILISATION_PERCENT
from prm.domain.dtos import (
    TeamSearchAllocationFact,
    TeamSearchCandidate,
    TeamSearchSkill,
    TeamSlotFilters,
)
from prm.domain.enums import ActivityTag, ProficiencyLevel, ResourceWorkStatus, SkillCategory

_PROFICIENCY_ORDER: dict[ProficiencyLevel, int] = {
    ProficiencyLevel.BEGINNER: 0,
    ProficiencyLevel.INTERMEDIATE: 1,
    ProficiencyLevel.ADVANCED: 2,
}


class TeamCandidateSearchService:
    """Return active direct-report engineers matching only non-empty slot filters."""

    def __init__(
        self,
        user_repository: UserRepository,
        user_skill_repository: UserSkillRepository,
        skill_repository: SkillRepository,
        allocation_repository: AllocationRepository,
        project_repository: ProjectRepository,
        timesheet_repository: TimesheetRepository,
        *,
        max_weekly_hours: int,
    ) -> None:
        self._users = user_repository
        self._user_skills = user_skill_repository
        self._skills = skill_repository
        self._allocations = allocation_repository
        self._projects = project_repository
        self._timesheets = timesheet_repository
        self._max_weekly_hours = max_weekly_hours

    def search_candidates(
        self,
        manager_user_id: int,
        filters: TeamSlotFilters,
        *,
        exclude_user_ids: set[int] | frozenset[int] = frozenset(),
        exclude_project_id: int | None = None,
        as_of: date | None = None,
    ) -> tuple[TeamSearchCandidate, ...]:
        reference = as_of or date.today()
        matched: list[TeamSearchCandidate] = []

        for engineer in self._users.list_by_manager_id(
            manager_user_id,
            active_only=True,
        ):
            if engineer.id in exclude_user_ids:
                continue

            candidate = self._to_candidate(
                engineer.id,
                full_name=engineer.full_name,
                department=engineer.department_name or "",
                designation=engineer.designation_name or "",
                utilisation_percent=engineer.utilisation_percent or 0,
                work_status=engineer.work_status or ResourceWorkStatus.BENCH,
                exclude_project_id=exclude_project_id,
                as_of=reference,
            )
            if self._matches_filters(candidate, filters):
                matched.append(candidate)

        return tuple(matched)

    def _to_candidate(
        self,
        user_id: int,
        *,
        full_name: str,
        department: str,
        designation: str,
        utilisation_percent: int,
        work_status: ResourceWorkStatus,
        exclude_project_id: int | None,
        as_of: date,
    ) -> TeamSearchCandidate:
        free_hours = self._free_hours_per_week(utilisation_percent)
        return TeamSearchCandidate(
            user_id=user_id,
            full_name=full_name,
            department=department,
            designation=designation,
            skills=self._skills_for_user(user_id),
            utilisation_percent=utilisation_percent,
            free_hours_per_week=free_hours,
            work_status=work_status,
            other_allocations=self._other_allocations(user_id, exclude_project_id),
            recent_activity_tags=tuple(
                self._timesheets.list_recent_activity_tags(
                    user_id,
                    weeks=4,
                    as_of=as_of,
                )
            ),
        )

    def _skills_for_user(self, user_id: int) -> tuple[TeamSearchSkill, ...]:
        skills: list[TeamSearchSkill] = []
        for assignment in self._user_skills.list_for_user(user_id):
            skill = self._skills.find_by_id(assignment.skill_id)
            if skill is not None:
                skills.append(
                    TeamSearchSkill(
                        name=skill.name,
                        category=skill.category,
                        proficiency=assignment.proficiency,
                    )
                )
        return tuple(skills)

    def _other_allocations(
        self,
        user_id: int,
        exclude_project_id: int | None,
    ) -> tuple[TeamSearchAllocationFact, ...]:
        facts: list[TeamSearchAllocationFact] = []
        for allocation in self._allocations.find_active_by_user(user_id):
            if exclude_project_id is not None and allocation.project_id == exclude_project_id:
                continue
            project = self._projects.find_by_id(allocation.project_id)
            project_name = project.name if project is not None else "Unknown project"
            facts.append(
                TeamSearchAllocationFact(
                    project_name=project_name,
                    utilisation_percent=allocation.utilisation_percent,
                    to_date=allocation.to_date,
                )
            )
        return tuple(facts)

    def _matches_filters(
        self,
        candidate: TeamSearchCandidate,
        filters: TeamSlotFilters,
    ) -> bool:
        if filters.department is not None and not self._text_matches(
            candidate.department,
            filters.department,
        ):
            return False
        if filters.designation is not None and not self._text_matches(
            candidate.designation,
            filters.designation,
        ):
            return False
        if filters.work_status is not None and candidate.work_status != filters.work_status:
            return False
        if filters.min_free_hours_per_week is not None:
            if candidate.free_hours_per_week < filters.min_free_hours_per_week:
                return False
        if filters.activity_tags and not self._has_activity_tag_overlap(
            candidate,
            filters.activity_tags,
        ):
            return False
        if not self._matches_skill_filters(candidate, filters):
            return False
        return True

    def _matches_skill_filters(
        self,
        candidate: TeamSearchCandidate,
        filters: TeamSlotFilters,
    ) -> bool:
        has_skill_filter = (
            filters.skill_name is not None
            or filters.skill_category is not None
            or filters.min_proficiency is not None
        )
        if not has_skill_filter:
            return True

        for skill in candidate.skills:
            if not self._skill_matches_name(skill, filters.skill_name):
                continue
            if not self._skill_matches_category(skill, filters.skill_category):
                continue
            if not self._skill_matches_proficiency(skill, filters):
                continue
            return True
        return False

    @staticmethod
    def _skill_matches_name(skill: TeamSearchSkill, skill_name: str | None) -> bool:
        if skill_name is None:
            return True
        return skill.name.casefold() == skill_name.casefold()

    @staticmethod
    def _skill_matches_category(
        skill: TeamSearchSkill,
        skill_category: SkillCategory | None,
    ) -> bool:
        if skill_category is None:
            return True
        return skill.category == skill_category

    @staticmethod
    def _skill_matches_proficiency(
        skill: TeamSearchSkill,
        filters: TeamSlotFilters,
    ) -> bool:
        if filters.min_proficiency is None:
            return True
        return (
            _PROFICIENCY_ORDER[skill.proficiency]
            >= _PROFICIENCY_ORDER[filters.min_proficiency]
        )

    @staticmethod
    def _text_matches(actual: str, expected: str) -> bool:
        return actual.casefold() == expected.casefold()

    @staticmethod
    def _has_activity_tag_overlap(
        candidate: TeamSearchCandidate,
        required_tags: tuple[ActivityTag, ...],
    ) -> bool:
        candidate_tags = {tag.casefold() for tag in candidate.recent_activity_tags}
        for tag in required_tags:
            if tag.value.casefold() in candidate_tags:
                return True
        return False

    def _free_hours_per_week(self, utilisation_percent: int) -> int:
        availability_percent = max(0, MAX_UTILISATION_PERCENT - utilisation_percent)
        return (availability_percent * self._max_weekly_hours) // MAX_UTILISATION_PERCENT
