"""Orchestrate LLM team-plan parsing and deterministic team assignment."""

from datetime import date

from prm.application.authorization_service import AuthorizationService
from prm.application.protocols import LLMClient
from prm.application.team_assignment_service import TeamAssignmentService
from prm.domain.dtos import TeamAssignmentResult, TeamPlanParseContext
from prm.domain.exceptions import ValidationError


class TeamMatchService:
    """Parse a plain-English requirement, then assign the manager's team in one pass."""

    def __init__(
        self,
        authorization: AuthorizationService,
        llm_client: LLMClient,
        assignment_service: TeamAssignmentService,
    ) -> None:
        self._authorization = authorization
        self._llm = llm_client
        self._assignment = assignment_service

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
        return self._assignment.assign_team(
            manager_user_id,
            project_id,
            plan,
            requirement=cleaned,
            as_of=as_of,
        )
