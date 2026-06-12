"""Unit tests for TeamMatchService."""

from datetime import date

import pytest
from sqlalchemy.orm import Session

from prm.application.authorization_service import AuthorizationService
from prm.application.team_assignment_service import TeamAssignmentService
from prm.application.team_candidate_search_service import TeamCandidateSearchService
from prm.application.team_match_service import TeamMatchService
from prm.domain.dtos import (
    TeamAssignmentReason,
    TeamPlan,
    TeamSlotFilters,
    TeamSlotSpec,
)
from prm.domain.enums import (
    ProficiencyLevel,
    ProjectStatus,
    ResourceWorkStatus,
    Role,
    SkillCategory,
)
from prm.domain.exceptions import UnauthorizedError, ValidationError
from prm.infrastructure.db.repositories import (
    SqlAlchemyAllocationRepository,
    SqlAlchemyProjectRepository,
    SqlAlchemySkillRepository,
    SqlAlchemyUserRepository,
    SqlAlchemyUserSkillRepository,
)
from prm.infrastructure.llm.fake_client import FakeLlmClient
from tests.unit.engineer_fixtures import (
    create_allocation_tables,
    create_memory_session,
    create_skill_tables,
    create_user,
    seed_rbac,
    set_engineer_status,
)


class _FakeTimesheetRepository:
    def list_recent_activity_tags(
        self,
        user_id: int,
        *,
        weeks: int = 4,
        as_of: date | None = None,
    ) -> list[str]:
        _ = user_id, weeks, as_of
        return []


def _session() -> Session:
    session = create_memory_session(include_project=True)
    create_skill_tables(session)
    create_allocation_tables(session)
    return session


def _match_service(
    session: Session,
    *,
    fake_llm: FakeLlmClient,
) -> TeamMatchService:
    project_repo = SqlAlchemyProjectRepository(session)
    search = TeamCandidateSearchService(
        user_repository=SqlAlchemyUserRepository(session),
        user_skill_repository=SqlAlchemyUserSkillRepository(session),
        skill_repository=SqlAlchemySkillRepository(session),
        allocation_repository=SqlAlchemyAllocationRepository(session),
        project_repository=project_repo,
        timesheet_repository=_FakeTimesheetRepository(),
        max_weekly_hours=40,
    )
    assignment = TeamAssignmentService(
        search_service=search,
        authorization=AuthorizationService(project_repo),
        max_weekly_hours=40,
    )
    return TeamMatchService(
        authorization=AuthorizationService(project_repo),
        llm_client=fake_llm,
        assignment_service=assignment,
        search_service=search,
    )


def _seed_manager_project(session: Session) -> tuple[int, int]:
    seed_rbac(session)
    manager_id = create_user(
        session,
        username="ankit",
        email="ankit@example.test",
        full_name="Ankit Shah",
        role=Role.MANAGER,
    )
    project = SqlAlchemyProjectRepository(session).create(
        name="Banking Portal",
        description="Demo",
        start_date=date(2026, 3, 1),
        end_date=date(2026, 12, 31),
        status=ProjectStatus.ACTIVE,
        manager_user_id=manager_id,
    )
    return manager_id, project.id


def _banking_plan() -> TeamPlan:
    return TeamPlan(
        team_slots=(
            TeamSlotSpec(
                slot_id=1,
                role_label="Senior Java Developer",
                headcount=1,
                filters=TeamSlotFilters(
                    skill_category=SkillCategory.BACKEND,
                    skill_name="Java",
                    min_proficiency=ProficiencyLevel.ADVANCED,
                ),
            ),
        ),
    )


def test_match_team_parses_requirement_and_assigns() -> None:
    session = _session()
    manager_id, project_id = _seed_manager_project(session)
    engineer_id = create_user(
        session,
        full_name="Ravi Kumar",
        username="ravi.kumar",
        email="ravi@example.test",
        role=Role.ENGINEER,
        manager_id=manager_id,
    )
    set_engineer_status(
        session,
        engineer_id,
        utilisation_percent=0,
        work_status=ResourceWorkStatus.BENCH,
    )
    skill = SqlAlchemySkillRepository(session).get_or_create(
        name="Java",
        category=SkillCategory.BACKEND,
    )
    SqlAlchemyUserSkillRepository(session).assign(
        user_id=engineer_id,
        skill_id=skill.id,
        proficiency=ProficiencyLevel.ADVANCED,
    )
    fake_llm = FakeLlmClient(team_plan=_banking_plan())
    requirement = "Banking portal needs a Senior Java Developer"

    result = _match_service(session, fake_llm=fake_llm).match_team(
        manager_id,
        project_id,
        requirement,
    )

    assert len(fake_llm.parse_team_plan_calls) == 1
    assert fake_llm.parse_team_plan_calls[0].requirement == requirement
    assert fake_llm.parse_team_plan_calls[0].project_name == "Banking Portal"
    assert result.requirement == requirement
    assert len(result.assignments) == 1
    assert result.assignments[0].user_id == engineer_id
    assert len(fake_llm.explain_team_assignments_calls) == 1
    assert "strong fit" in result.assignments[0].reason


def test_match_team_uses_llm_reason_when_preset() -> None:
    session = _session()
    manager_id, project_id = _seed_manager_project(session)
    engineer_id = create_user(
        session,
        full_name="Ravi Kumar",
        username="ravi.kumar",
        email="ravi@example.test",
        role=Role.ENGINEER,
        manager_id=manager_id,
    )
    set_engineer_status(
        session,
        engineer_id,
        utilisation_percent=0,
        work_status=ResourceWorkStatus.BENCH,
    )
    skill = SqlAlchemySkillRepository(session).get_or_create(
        name="Java",
        category=SkillCategory.BACKEND,
    )
    SqlAlchemyUserSkillRepository(session).assign(
        user_id=engineer_id,
        skill_id=skill.id,
        proficiency=ProficiencyLevel.ADVANCED,
    )
    fake_llm = FakeLlmClient(
        team_plan=_banking_plan(),
        explain_reasons=(
            TeamAssignmentReason(
                slot_id=1,
                position=1,
                user_id=engineer_id,
                reason="Ravi brings Advanced Java and is fully available on bench.",
            ),
        ),
    )

    result = _match_service(session, fake_llm=fake_llm).match_team(
        manager_id,
        project_id,
        "Banking portal needs a Senior Java Developer",
    )

    assert result.assignments[0].reason == (
        "Ravi brings Advanced Java and is fully available on bench."
    )


def test_match_team_keeps_template_reason_when_explain_fails() -> None:
    session = _session()
    manager_id, project_id = _seed_manager_project(session)
    engineer_id = create_user(
        session,
        full_name="Ravi Kumar",
        username="ravi.kumar",
        email="ravi@example.test",
        role=Role.ENGINEER,
        manager_id=manager_id,
    )
    set_engineer_status(
        session,
        engineer_id,
        utilisation_percent=0,
        work_status=ResourceWorkStatus.BENCH,
    )
    skill = SqlAlchemySkillRepository(session).get_or_create(
        name="Java",
        category=SkillCategory.BACKEND,
    )
    SqlAlchemyUserSkillRepository(session).assign(
        user_id=engineer_id,
        skill_id=skill.id,
        proficiency=ProficiencyLevel.ADVANCED,
    )
    fake_llm = FakeLlmClient(
        team_plan=_banking_plan(),
        fail_explain_team_assignments=True,
    )

    result = _match_service(session, fake_llm=fake_llm).match_team(
        manager_id,
        project_id,
        "Banking portal needs a Senior Java Developer",
    )

    assert result.assignments[0].user_id == engineer_id
    assert "matches Senior Java Developer" in result.assignments[0].reason


def test_match_team_rejects_blank_requirement() -> None:
    session = _session()
    manager_id, project_id = _seed_manager_project(session)
    fake_llm = FakeLlmClient(team_plan=_banking_plan())

    with pytest.raises(ValidationError, match="Requirement is required"):
        _match_service(session, fake_llm=fake_llm).match_team(
            manager_id,
            project_id,
            "   ",
        )

    assert fake_llm.parse_team_plan_calls == []


def test_match_team_requires_project_owner() -> None:
    session = _session()
    manager_id, project_id = _seed_manager_project(session)
    other_manager_id = create_user(
        session,
        full_name="Other Manager",
        username="other.manager",
        email="other@example.test",
        role=Role.MANAGER,
    )
    fake_llm = FakeLlmClient(team_plan=_banking_plan())

    with pytest.raises(UnauthorizedError, match="project owner"):
        _match_service(session, fake_llm=fake_llm).match_team(
            other_manager_id,
            project_id,
            "Need a Java developer",
        )

    assert fake_llm.parse_team_plan_calls == []
