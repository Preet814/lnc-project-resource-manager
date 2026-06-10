"""Unit tests for SkillMatchService."""

from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from prm.application.authorization_service import AuthorizationService
from prm.application.skill_match_service import SkillMatchService
from prm.domain.dtos import SkillMatchResult
from prm.domain.enums import (
    EmployeeWorkStatus,
    ProficiencyLevel,
    ProjectStatus,
    Role,
    SkillCategory,
)
from prm.domain.exceptions import UnauthorizedError, ValidationError
from prm.infrastructure.db.models import (
    EmployeeModel,
    EmployeeSkillModel,
    ProjectModel,
    SkillModel,
    UserModel,
)
from prm.infrastructure.db.repositories import (
    SqlAlchemyEmployeeRepository,
    SqlAlchemyEmployeeSkillRepository,
    SqlAlchemyProjectRepository,
    SqlAlchemySkillRepository,
    SqlAlchemyUserRepository,
)
from prm.infrastructure.llm.fake_client import FakeLlmClient
from prm.infrastructure.security.password import BcryptPasswordHasher


class _FakeTimesheetRepository:
    def __init__(self, tags: list[str] | None = None) -> None:
        self._tags = tags or []

    def list_recent_activity_tags(
        self,
        employee_id: int,
        *,
        weeks: int = 4,
        as_of: date | None = None,
    ) -> list[str]:
        _ = employee_id, weeks, as_of
        return list(self._tags)


def _session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    UserModel.__table__.create(engine, checkfirst=True)
    EmployeeModel.__table__.create(engine, checkfirst=True)
    ProjectModel.__table__.create(engine, checkfirst=True)
    SkillModel.__table__.create(engine, checkfirst=True)
    EmployeeSkillModel.__table__.create(engine, checkfirst=True)
    return Session(engine)


def _service(
    session: Session,
    *,
    llm: FakeLlmClient,
    max_weekly_hours: int = 40,
    tags: list[str] | None = None,
) -> SkillMatchService:
    project_repo = SqlAlchemyProjectRepository(session)
    return SkillMatchService(
        employee_repository=SqlAlchemyEmployeeRepository(session),
        employee_skill_repository=SqlAlchemyEmployeeSkillRepository(session),
        skill_repository=SqlAlchemySkillRepository(session),
        timesheet_repository=_FakeTimesheetRepository(tags),
        authorization=AuthorizationService(project_repo),
        llm_client=llm,
        max_weekly_hours=max_weekly_hours,
    )


def _seed_manager_and_project(session: Session) -> tuple[int, int]:
    user_repo = SqlAlchemyUserRepository(session)
    hasher = BcryptPasswordHasher()
    manager = user_repo.create(
        full_name="Ankit Shah",
        username="ankit",
        email="ankit@example.test",
        password_hash=hasher.hash("TempPass1"),
        role=Role.MANAGER,
    )
    project_repo = SqlAlchemyProjectRepository(session)
    project = project_repo.create(
        name="Alpha Portal",
        description="Customer portal rewrite",
        start_date=date(2026, 3, 1),
        end_date=date(2026, 6, 30),
        status=ProjectStatus.ACTIVE,
        manager_user_id=manager.id,
    )
    return manager.id, project.id


def _seed_employee(
    session: Session,
    *,
    manager_user_id: int,
    full_name: str,
    email: str,
    username: str,
    utilisation_percent: int,
    work_status: EmployeeWorkStatus = EmployeeWorkStatus.BENCH,
) -> int:
    user_repo = SqlAlchemyUserRepository(session)
    hasher = BcryptPasswordHasher()
    user = user_repo.create(
        full_name=full_name,
        username=username,
        email=email,
        password_hash=hasher.hash("TempPass1"),
        role=Role.EMPLOYEE,
    )
    employee_repo = SqlAlchemyEmployeeRepository(session)
    employee = employee_repo.create(
        user_id=user.id,
        full_name=full_name,
        email=email,
        department="Backend",
        designation="Developer",
    )
    employee_repo.update_utilisation_and_status(
        employee.id,
        current_utilisation_percent=utilisation_percent,
        work_status=work_status,
    )
    employee_repo.set_manager_id(employee.id, manager_id=manager_user_id)
    return employee.id


def test_find_matches_returns_llm_results_for_qualified_candidates() -> None:
    session = _session()
    manager_id, project_id = _seed_manager_and_project(session)
    bench_id = _seed_employee(
        session,
        manager_user_id=manager_id,
        full_name="Anil Mehta",
        email="anil@example.test",
        username="anil.mehta",
        utilisation_percent=0,
    )
    _seed_employee(
        session,
        manager_user_id=manager_id,
        full_name="Fully Booked",
        email="booked@example.test",
        username="fully.booked",
        utilisation_percent=100,
        work_status=EmployeeWorkStatus.ALLOCATED,
    )
    skill_repo = SqlAlchemySkillRepository(session)
    skill = skill_repo.create(name="Microservices", category=SkillCategory.BACKEND)
    employee_skill_repo = SqlAlchemyEmployeeSkillRepository(session)
    employee_skill_repo.assign(
        employee_id=bench_id,
        skill_id=skill.id,
        proficiency=ProficiencyLevel.ADVANCED,
    )

    llm = FakeLlmClient(
        rank_results=(
            SkillMatchResult(
                employee_id=bench_id,
                employee_name="Anil Mehta",
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
    assert result.matches[0].employee_name == "Anil Mehta"
    assert len(llm.rank_calls) == 1
    _, candidates = llm.rank_calls[0]
    assert len(candidates) == 1
    assert candidates[0].employee_id == bench_id
    assert candidates[0].free_hours_per_week == 40


def test_find_matches_skips_llm_when_no_part_time_capacity() -> None:
    session = _session()
    manager_id, project_id = _seed_manager_and_project(session)
    _seed_employee(
        session,
        manager_user_id=manager_id,
        full_name="Dev Patel",
        email="dev@example.test",
        username="dev.patel",
        utilisation_percent=75,
        work_status=EmployeeWorkStatus.ALLOCATED,
    )
    llm = FakeLlmClient()

    result = _service(session, llm=llm).find_matches(
        manager_id,
        project_id,
        "Need 20 hrs/week for UI testing",
    )

    assert result.total == 0
    assert result.matches == ()
    assert result.message == "No employees have at least 20 free hours per week."
    assert llm.rank_calls == []


def test_find_matches_rejects_blank_requirement() -> None:
    session = _session()
    manager_id, project_id = _seed_manager_and_project(session)
    llm = FakeLlmClient()

    with pytest.raises(ValidationError, match="Requirement is required"):
        _service(session, llm=llm).find_matches(manager_id, project_id, "   ")


def test_find_matches_requires_project_owner() -> None:
    session = _session()
    manager_id, _project_id = _seed_manager_and_project(session)
    user_repo = SqlAlchemyUserRepository(session)
    hasher = BcryptPasswordHasher()
    other_manager = user_repo.create(
        full_name="Other Manager",
        username="other.manager",
        email="other@example.test",
        password_hash=hasher.hash("TempPass1"),
        role=Role.MANAGER,
    )
    project_repo = SqlAlchemyProjectRepository(session)
    other_project = project_repo.create(
        name="Beta CRM",
        description="CRM rollout",
        start_date=date(2026, 4, 1),
        end_date=date(2026, 8, 15),
        status=ProjectStatus.ACTIVE,
        manager_user_id=other_manager.id,
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
    user_repo = SqlAlchemyUserRepository(session)
    hasher = BcryptPasswordHasher()
    other_manager = user_repo.create(
        full_name="Other Manager",
        username="other.manager",
        email="other@example.test",
        password_hash=hasher.hash("TempPass1"),
        role=Role.MANAGER,
    )
    other_team_employee_id = _seed_employee(
        session,
        manager_user_id=other_manager.id,
        full_name="Other Team Dev",
        email="other.team@example.test",
        username="other.team",
        utilisation_percent=0,
    )
    skill_repo = SqlAlchemySkillRepository(session)
    skill = skill_repo.create(name="Microservices", category=SkillCategory.BACKEND)
    employee_skill_repo = SqlAlchemyEmployeeSkillRepository(session)
    employee_skill_repo.assign(
        employee_id=other_team_employee_id,
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
