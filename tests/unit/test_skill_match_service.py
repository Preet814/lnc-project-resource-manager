"""Unit tests for SkillMatchService."""

from datetime import date

import pytest
from sqlalchemy.orm import Session

from prm.application.authorization_service import AuthorizationService
from prm.application.skill_match_service import SkillMatchService
from prm.domain.dtos import SkillMatchResult
from prm.domain.enums import (
    ProficiencyLevel,
    ProjectStatus,
    ResourceWorkStatus,
    Role,
    SkillCategory,
)
from prm.domain.exceptions import UnauthorizedError, ValidationError
from prm.infrastructure.db.repositories import (
    SqlAlchemyProjectRepository,
    SqlAlchemySkillRepository,
    SqlAlchemyUserRepository,
    SqlAlchemyUserSkillRepository,
)
from prm.infrastructure.llm.fake_client import FakeLlmClient
from tests.unit.engineer_fixtures import (
    create_memory_session,
    create_skill_tables,
    create_user,
    seed_rbac,
    set_engineer_status,
)


class _FakeTimesheetRepository:
    def __init__(self, tags: list[str] | None = None) -> None:
        self._tags = tags or []

    def list_recent_activity_tags(
        self,
        user_id: int,
        *,
        weeks: int = 4,
        as_of: date | None = None,
    ) -> list[str]:
        _ = user_id, weeks, as_of
        return list(self._tags)


def _session() -> Session:
    session = create_memory_session(include_project=True)
    create_skill_tables(session)
    return session


def _service(
    session: Session,
    *,
    llm: FakeLlmClient,
    max_weekly_hours: int = 40,
    tags: list[str] | None = None,
) -> SkillMatchService:
    project_repo = SqlAlchemyProjectRepository(session)
    return SkillMatchService(
        user_repository=SqlAlchemyUserRepository(session),
        user_skill_repository=SqlAlchemyUserSkillRepository(session),
        skill_repository=SqlAlchemySkillRepository(session),
        timesheet_repository=_FakeTimesheetRepository(tags),
        authorization=AuthorizationService(project_repo),
        llm_client=llm,
        max_weekly_hours=max_weekly_hours,
    )


def _seed_manager_and_project(session: Session) -> tuple[int, int]:
    seed_rbac(session)
    manager_id = create_user(
        session,
        username="ankit",
        email="ankit@example.test",
        full_name="Ankit Shah",
        role=Role.MANAGER,
    )
    project_repo = SqlAlchemyProjectRepository(session)
    project = project_repo.create(
        name="Alpha Portal",
        description="Customer portal rewrite",
        start_date=date(2026, 3, 1),
        end_date=date(2026, 6, 30),
        status=ProjectStatus.ACTIVE,
        manager_user_id=manager_id,
    )
    return manager_id, project.id


def _seed_engineer(
    session: Session,
    *,
    manager_user_id: int,
    full_name: str,
    email: str,
    username: str,
    utilisation_percent: int,
    work_status: ResourceWorkStatus = ResourceWorkStatus.BENCH,
) -> int:
    user_id = create_user(
        session,
        full_name=full_name,
        username=username,
        email=email,
        role=Role.ENGINEER,
        manager_id=manager_user_id,
    )
    set_engineer_status(
        session,
        user_id,
        utilisation_percent=utilisation_percent,
        work_status=work_status,
    )
    return user_id


def test_find_matches_returns_llm_results_for_qualified_candidates() -> None:
    session = _session()
    manager_id, project_id = _seed_manager_and_project(session)
    bench_id = _seed_engineer(
        session,
        manager_user_id=manager_id,
        full_name="Anil Mehta",
        email="anil@example.test",
        username="anil.mehta",
        utilisation_percent=0,
    )
    _seed_engineer(
        session,
        manager_user_id=manager_id,
        full_name="Fully Booked",
        email="booked@example.test",
        username="fully.booked",
        utilisation_percent=100,
        work_status=ResourceWorkStatus.ALLOCATED,
    )
    skill_repo = SqlAlchemySkillRepository(session)
    skill = skill_repo.create(name="Microservices", category=SkillCategory.BACKEND)
    user_skill_repo = SqlAlchemyUserSkillRepository(session)
    user_skill_repo.assign(
        user_id=bench_id,
        skill_id=skill.id,
        proficiency=ProficiencyLevel.ADVANCED,
    )

    llm = FakeLlmClient(
        rank_results=(
            SkillMatchResult(
                user_id=bench_id,
                user_name="Anil Mehta",
                reason="Strong microservices fit and fully available.",
                suggested_allocation_percent=50,
                free_hours_per_week=40,
            ),
        ),
    )
    service = _service(session, llm=llm, tags=["Microservices"])

    result = service.find_matches(
        manager_id,
        project_id,
        "Java developer with microservices experience",
    )

    assert result.total == 1
    assert result.message is None
    assert result.matches[0].user_name == "Anil Mehta"
    assert len(llm.rank_calls) == 1
    _, candidates = llm.rank_calls[0]
    assert len(candidates) == 1
    assert candidates[0].user_id == bench_id
    assert candidates[0].free_hours_per_week == 40


def test_find_matches_skips_llm_when_no_part_time_capacity() -> None:
    session = _session()
    manager_id, project_id = _seed_manager_and_project(session)
    _seed_engineer(
        session,
        manager_user_id=manager_id,
        full_name="Dev Patel",
        email="dev@example.test",
        username="dev.patel",
        utilisation_percent=75,
        work_status=ResourceWorkStatus.ALLOCATED,
    )
    llm = FakeLlmClient()

    result = _service(session, llm=llm).find_matches(
        manager_id,
        project_id,
        "Need 20 hrs/week for UI testing",
    )

    assert result.total == 0
    assert result.matches == ()
    assert result.message == "No engineers have at least 20 free hours per week."
    assert llm.rank_calls == []


def test_find_matches_rejects_non_allocatable_project() -> None:
    session = _session()
    manager_id, _project_id = _seed_manager_and_project(session)
    project_repo = SqlAlchemyProjectRepository(session)
    completed = project_repo.create(
        name="Finished Portal",
        description="Delivered",
        start_date=date(2026, 1, 1),
        end_date=date(2026, 6, 30),
        status=ProjectStatus.COMPLETED,
        manager_user_id=manager_id,
    )
    llm = FakeLlmClient()

    with pytest.raises(ValidationError, match="ACTIVE or PLANNED"):
        _service(session, llm=llm).find_matches(
            manager_id,
            completed.id,
            "Need a backend developer",
        )


def test_find_matches_rejects_blank_requirement() -> None:
    session = _session()
    manager_id, project_id = _seed_manager_and_project(session)
    llm = FakeLlmClient()

    with pytest.raises(ValidationError, match="Requirement is required"):
        _service(session, llm=llm).find_matches(manager_id, project_id, "   ")


def test_find_matches_requires_project_owner() -> None:
    session = _session()
    manager_id, _project_id = _seed_manager_and_project(session)
    seed_rbac(session)
    other_manager_id = create_user(
        session,
        full_name="Other Manager",
        username="other.manager",
        email="other@example.test",
        role=Role.MANAGER,
    )
    project_repo = SqlAlchemyProjectRepository(session)
    other_project = project_repo.create(
        name="Beta CRM",
        description="CRM rollout",
        start_date=date(2026, 4, 1),
        end_date=date(2026, 8, 15),
        status=ProjectStatus.ACTIVE,
        manager_user_id=other_manager_id,
    )
    llm = FakeLlmClient()

    with pytest.raises(UnauthorizedError, match="project owner"):
        _service(session, llm=llm).find_matches(
            manager_id,
            other_project.id,
            "Need a backend developer",
        )


def test_find_matches_excludes_employees_not_on_manager_team() -> None:
    session = _session()
    manager_id, project_id = _seed_manager_and_project(session)
    seed_rbac(session)
    other_manager_id = create_user(
        session,
        full_name="Other Manager",
        username="other.manager",
        email="other@example.test",
        role=Role.MANAGER,
    )
    other_team_user_id = _seed_engineer(
        session,
        manager_user_id=other_manager_id,
        full_name="Other Team Dev",
        email="other.team@example.test",
        username="other.team",
        utilisation_percent=0,
    )
    skill_repo = SqlAlchemySkillRepository(session)
    skill = skill_repo.create(name="Microservices", category=SkillCategory.BACKEND)
    user_skill_repo = SqlAlchemyUserSkillRepository(session)
    user_skill_repo.assign(
        user_id=other_team_user_id,
        skill_id=skill.id,
        proficiency=ProficiencyLevel.ADVANCED,
    )
    llm = FakeLlmClient()

    result = _service(session, llm=llm, tags=["Microservices"]).find_matches(
        manager_id,
        project_id,
        "Java developer with microservices experience",
    )

    assert result.total == 0
    assert result.matches == ()
    assert llm.rank_calls == []
