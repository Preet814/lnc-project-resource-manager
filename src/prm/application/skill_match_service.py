"""AI skill match use case with capacity pre-filter (BRD §4.2 AI, §4.5)."""

from datetime import date

from prm.application.authorization_service import AuthorizationService
from prm.application.protocols import (
    LLMClient,
    SkillRepository,
    TimesheetRepository,
    UserRepository,
    UserSkillRepository,
)
from prm.application.requirement_parser import parse_requested_hours_per_week
from prm.domain.constants import MAX_UTILISATION_PERCENT
from prm.domain.dtos import (
    SkillMatchCandidate,
    SkillMatchContext,
    SkillMatchListResult,
)
from prm.domain.exceptions import ValidationError


class SkillMatchService:
    """Load candidates, pre-filter by capacity, then rank via LLM."""

    def __init__(
        self,
        user_repository: UserRepository,
        user_skill_repository: UserSkillRepository,
        skill_repository: SkillRepository,
        timesheet_repository: TimesheetRepository,
        authorization: AuthorizationService,
        llm_client: LLMClient,
        *,
        max_weekly_hours: int,
    ) -> None:
        self._users = user_repository
        self._user_skills = user_skill_repository
        self._skills = skill_repository
        self._timesheets = timesheet_repository
        self._authorization = authorization
        self._llm = llm_client
        self._max_weekly_hours = max_weekly_hours

    def find_matches(
        self,
        manager_user_id: int,
        project_id: int,
        requirement: str,
        *,
        as_of: date | None = None,
    ) -> SkillMatchListResult:
        project = self._authorization.assert_project_owner(manager_user_id, project_id)
        if not project.allows_allocation():
            raise ValidationError(
                "Project must be ACTIVE or PLANNED to accept allocations."
            )

        cleaned = requirement.strip()
        if not cleaned:
            raise ValidationError("Requirement is required.")

        requested_hours = parse_requested_hours_per_week(cleaned)
        candidates = self._load_qualified_candidates(
            manager_user_id,
            requested_hours,
            as_of=as_of,
        )
        if not candidates:
            return SkillMatchListResult(
                project_id=project_id,
                requirement=cleaned,
                matches=(),
                total=0,
                message=self._no_candidates_message(requested_hours),
            )

        context = SkillMatchContext(
            project_id=project.id,
            project_name=project.name,
            requirement=cleaned,
            requested_hours_per_week=requested_hours,
        )
        matches = self._llm.rank_candidates(context, candidates)
        return SkillMatchListResult(
            project_id=project_id,
            requirement=cleaned,
            matches=matches,
            total=len(matches),
        )

    def _load_qualified_candidates(
        self,
        manager_user_id: int,
        requested_hours: int | None,
        *,
        as_of: date | None,
    ) -> tuple[SkillMatchCandidate, ...]:
        reference = as_of or date.today()
        qualified: list[SkillMatchCandidate] = []

        for engineer in self._users.list_by_manager_id(
            manager_user_id,
            active_only=True,
        ):
            utilisation = engineer.utilisation_percent or 0
            free_hours = self._free_hours_per_week(utilisation)
            if requested_hours is not None:
                if free_hours < requested_hours:
                    continue
            elif free_hours <= 0:
                continue

            qualified.append(
                SkillMatchCandidate(
                    user_id=engineer.id,
                    full_name=engineer.full_name,
                    skill_names=self._skill_names(engineer.id),
                    utilisation_percent=utilisation,
                    free_hours_per_week=free_hours,
                    recent_activity_tags=tuple(
                        self._timesheets.list_recent_activity_tags(
                            engineer.id,
                            weeks=4,
                            as_of=reference,
                        )
                    ),
                )
            )

        return tuple(qualified)

    def _free_hours_per_week(self, utilisation_percent: int) -> int:
        availability_percent = max(0, MAX_UTILISATION_PERCENT - utilisation_percent)
        return (availability_percent * self._max_weekly_hours) // MAX_UTILISATION_PERCENT

    def _skill_names(self, user_id: int) -> tuple[str, ...]:
        assignments = self._user_skills.list_for_user(user_id)
        names: list[str] = []
        for assignment in assignments:
            skill = self._skills.find_by_id(assignment.skill_id)
            if skill is not None:
                names.append(skill.name)
        return tuple(names)

    @staticmethod
    def _no_candidates_message(requested_hours: int | None) -> str:
        if requested_hours is not None:
            return f"No engineers have at least {requested_hours} free hours per week."
        return "No engineers with available capacity were found."
