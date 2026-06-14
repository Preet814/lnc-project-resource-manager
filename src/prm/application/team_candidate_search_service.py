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

_DESIGNATION_EQUIVALENTS: tuple[frozenset[str], ...] = (
    frozenset({"se", "software engineer"}),
    frozenset({"sse", "senior software engineer"}),
    frozenset({"jse", "junior software engineer"}),
)

_DEPARTMENT_ROLE_EQUIVALENTS: tuple[frozenset[str], ...] = (
    frozenset({"devops", "dev ops"}),
    frozenset({"qa", "quality assurance"}),
    frozenset({"backend", "back-end"}),
    frozenset({"frontend", "front-end"}),
)


class TeamCandidateSearchService:
    """Return active direct-report engineers; hard-filter only explicit constraints."""

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
            if self._passes_hard_filters(candidate, filters):
                matched.append(candidate)

        return tuple(matched)

    def score_candidate(
        self,
        filters: TeamSlotFilters,
        candidate: TeamSearchCandidate,
    ) -> tuple[int, int, int, int, int, int, int, int, int]:
        """Rank candidates: soft preferences first, then capacity and bench."""
        return (
            self._department_bonus(filters, candidate),
            self._designation_bonus(filters, candidate),
            self._skill_name_bonus(filters, candidate),
            self._skill_category_bonus(filters, candidate),
            self._proficiency_headroom(filters, candidate),
            self._activity_overlap_bonus(filters, candidate),
            candidate.free_hours_per_week,
            self._bench_bonus(filters, candidate),
            MAX_UTILISATION_PERCENT - candidate.utilisation_percent,
        )

    def meets_skill_requirements(
        self,
        filters: TeamSlotFilters,
        candidate: TeamSearchCandidate,
    ) -> bool:
        """True when the candidate satisfies explicit skill filters (if any)."""
        if filters.skill_name is None and filters.skill_category is None:
            return True
        if filters.skill_name is not None:
            for skill in candidate.skills:
                if skill.name.casefold() != filters.skill_name.casefold():
                    continue
                if (
                    filters.skill_category is not None
                    and skill.category != filters.skill_category
                ):
                    continue
                if self._skill_meets_proficiency(skill, filters):
                    return True
            return False
        for skill in candidate.skills:
            if skill.category != filters.skill_category:
                continue
            if self._skill_meets_proficiency(skill, filters):
                return True
        return False

    def _passes_hard_filters(
        self,
        candidate: TeamSearchCandidate,
        filters: TeamSlotFilters,
    ) -> bool:
        if filters.work_status is not None and candidate.work_status != filters.work_status:
            return False
        if filters.min_free_hours_per_week is not None:
            if candidate.free_hours_per_week < filters.min_free_hours_per_week:
                return False
        return True

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

    def _department_bonus(
        self,
        filters: TeamSlotFilters,
        candidate: TeamSearchCandidate,
    ) -> int:
        if filters.department is None:
            return 0
        if self._department_matches(candidate.department, filters.department):
            return 100
        return 0

    def _designation_bonus(
        self,
        filters: TeamSlotFilters,
        candidate: TeamSearchCandidate,
    ) -> int:
        if filters.designation is None:
            return 0
        if self._designation_matches(candidate.designation, filters.designation):
            return 80
        return 0

    def _skill_name_bonus(
        self,
        filters: TeamSlotFilters,
        candidate: TeamSearchCandidate,
    ) -> int:
        if filters.skill_name is None:
            return 0
        for skill in candidate.skills:
            if skill.name.casefold() == filters.skill_name.casefold():
                if filters.skill_category is not None and skill.category != filters.skill_category:
                    continue
                if not self._skill_meets_proficiency(skill, filters):
                    continue
                return 60
        return 0

    def _skill_category_bonus(
        self,
        filters: TeamSlotFilters,
        candidate: TeamSearchCandidate,
    ) -> int:
        if filters.skill_category is None or filters.skill_name is not None:
            return 0
        for skill in candidate.skills:
            if skill.category != filters.skill_category:
                continue
            if not self._skill_meets_proficiency(skill, filters):
                continue
            return 40
        return 0

    def _proficiency_headroom(
        self,
        filters: TeamSlotFilters,
        candidate: TeamSearchCandidate,
    ) -> int:
        if filters.min_proficiency is None:
            return 0
        best = 0
        for skill in candidate.skills:
            if filters.skill_name is not None:
                if skill.name.casefold() != filters.skill_name.casefold():
                    continue
            if filters.skill_category is not None and skill.category != filters.skill_category:
                continue
            headroom = (
                _PROFICIENCY_ORDER[skill.proficiency]
                - _PROFICIENCY_ORDER[filters.min_proficiency]
            )
            if headroom >= 0:
                best = max(best, headroom + 1)
        return best

    @staticmethod
    def _skill_meets_proficiency(
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
    def _bench_bonus(
        filters: TeamSlotFilters,
        candidate: TeamSearchCandidate,
    ) -> int:
        if filters.work_status is not None:
            return 0
        if candidate.work_status == ResourceWorkStatus.BENCH:
            return 1
        return 0

    @staticmethod
    def _activity_overlap_bonus(
        filters: TeamSlotFilters,
        candidate: TeamSearchCandidate,
    ) -> int:
        if not filters.activity_tags:
            return 0
        candidate_tags = {tag.casefold() for tag in candidate.recent_activity_tags}
        return sum(
            1 for tag in filters.activity_tags if tag.value.casefold() in candidate_tags
        )

    @classmethod
    def _department_matches(cls, actual: str, expected: str) -> bool:
        if cls._text_matches(actual, expected):
            return True
        actual_key = actual.casefold().strip()
        expected_key = expected.casefold().strip()
        for equivalents in _DEPARTMENT_ROLE_EQUIVALENTS:
            if actual_key in equivalents and expected_key in equivalents:
                return True
        return False

    @classmethod
    def _designation_matches(cls, actual: str, expected: str) -> bool:
        if cls._text_matches(actual, expected):
            return True
        actual_key = actual.casefold().strip()
        expected_key = expected.casefold().strip()
        for equivalents in _DESIGNATION_EQUIVALENTS:
            if actual_key in equivalents and expected_key in equivalents:
                return True
        return False

    @staticmethod
    def _text_matches(actual: str, expected: str) -> bool:
        return actual.casefold().strip() == expected.casefold().strip()

    def _free_hours_per_week(self, utilisation_percent: int) -> int:
        availability_percent = max(0, MAX_UTILISATION_PERCENT - utilisation_percent)
        return (availability_percent * self._max_weekly_hours) // MAX_UTILISATION_PERCENT
