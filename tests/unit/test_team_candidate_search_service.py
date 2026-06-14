"""Unit tests for TeamCandidateSearchService."""

from datetime import date

from sqlalchemy.orm import Session

from prm.application.team_candidate_search_service import TeamCandidateSearchService
from prm.domain.dtos import TeamSlotFilters
from prm.domain.enums import (
    ActivityTag,
    ProficiencyLevel,
    ProjectStatus,
    ResourceWorkStatus,
    Role,
    SkillCategory,
    UserAccountStatus,
)
from prm.infrastructure.db.repositories import (
    SqlAlchemyAllocationRepository,
    SqlAlchemyProjectRepository,
    SqlAlchemySkillRepository,
    SqlAlchemyUserRepository,
    SqlAlchemyUserSkillRepository,
)
from tests.unit.engineer_fixtures import (
    create_allocation_tables,
    create_memory_session,
    create_skill_tables,
    create_user,
    seed_rbac,
    set_engineer_status,
)


class _FakeTimesheetRepository:
    def __init__(self, tags_by_user: dict[int, list[str]] | None = None) -> None:
        self._tags_by_user = tags_by_user or {}

    def list_recent_activity_tags(
        self,
        user_id: int,
        *,
        weeks: int = 4,
        as_of: date | None = None,
    ) -> list[str]:
        _ = weeks, as_of
        return list(self._tags_by_user.get(user_id, []))


def _session() -> Session:
    session = create_memory_session(include_project=True)
    create_skill_tables(session)
    create_allocation_tables(session)
    return session


def _service(
    session: Session,
    *,
    tags_by_user: dict[int, list[str]] | None = None,
    max_weekly_hours: int = 40,
) -> TeamCandidateSearchService:
    return TeamCandidateSearchService(
        user_repository=SqlAlchemyUserRepository(session),
        user_skill_repository=SqlAlchemyUserSkillRepository(session),
        skill_repository=SqlAlchemySkillRepository(session),
        allocation_repository=SqlAlchemyAllocationRepository(session),
        project_repository=SqlAlchemyProjectRepository(session),
        timesheet_repository=_FakeTimesheetRepository(tags_by_user),
        max_weekly_hours=max_weekly_hours,
    )


def _seed_manager_team(session: Session) -> tuple[int, int]:
    seed_rbac(session)
    manager_id = create_user(
        session,
        username="ankit",
        email="ankit@example.test",
        full_name="Ankit Shah",
        role=Role.MANAGER,
        department_name="Delivery",
        designation_name="Project Manager",
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


def _seed_engineer(
    session: Session,
    *,
    manager_user_id: int,
    full_name: str,
    email: str,
    username: str,
    utilisation_percent: int,
    work_status: ResourceWorkStatus,
    department_name: str = "Engineering",
    designation_name: str = "SE",
) -> int:
    user_id = create_user(
        session,
        full_name=full_name,
        username=username,
        email=email,
        role=Role.ENGINEER,
        manager_id=manager_user_id,
        department_name=department_name,
        designation_name=designation_name,
    )
    set_engineer_status(
        session,
        user_id,
        utilisation_percent=utilisation_percent,
        work_status=work_status,
    )
    return user_id


def _assign_skill(
    session: Session,
    *,
    user_id: int,
    skill_name: str,
    proficiency: ProficiencyLevel,
    category: SkillCategory = SkillCategory.BACKEND,
) -> None:
    skill_repo = SqlAlchemySkillRepository(session)
    skill = skill_repo.get_or_create(name=skill_name, category=category)
    SqlAlchemyUserSkillRepository(session).assign(
        user_id=user_id,
        skill_id=skill.id,
        proficiency=proficiency,
    )


def test_search_always_excludes_inactive_engineers() -> None:
    session = _session()
    manager_id, _project_id = _seed_manager_team(session)
    active_id = _seed_engineer(
        session,
        manager_user_id=manager_id,
        full_name="Active Dev",
        email="active@example.test",
        username="active.dev",
        utilisation_percent=0,
        work_status=ResourceWorkStatus.BENCH,
    )
    inactive_id = _seed_engineer(
        session,
        manager_user_id=manager_id,
        full_name="Inactive Dev",
        email="inactive@example.test",
        username="inactive.dev",
        utilisation_percent=0,
        work_status=ResourceWorkStatus.BENCH,
    )
    _assign_skill(
        session,
        user_id=active_id,
        skill_name="Java",
        proficiency=ProficiencyLevel.ADVANCED,
    )
    _assign_skill(
        session,
        user_id=inactive_id,
        skill_name="Java",
        proficiency=ProficiencyLevel.ADVANCED,
    )
    SqlAlchemyUserRepository(session).update_account_status(
        inactive_id,
        account_status=UserAccountStatus.INACTIVE,
    )

    results = _service(session).search_candidates(
        manager_id,
        TeamSlotFilters(skill_name="Java"),
    )

    assert {candidate.user_id for candidate in results} == {active_id}


def test_search_returns_both_engineers_for_skill_preferences() -> None:
    session = _session()
    manager_id, _project_id = _seed_manager_team(session)
    senior_id = _seed_engineer(
        session,
        manager_user_id=manager_id,
        full_name="Senior Dev",
        email="senior@example.test",
        username="senior.dev",
        utilisation_percent=0,
        work_status=ResourceWorkStatus.BENCH,
    )
    junior_id = _seed_engineer(
        session,
        manager_user_id=manager_id,
        full_name="Junior Dev",
        email="junior@example.test",
        username="junior.dev",
        utilisation_percent=0,
        work_status=ResourceWorkStatus.BENCH,
    )
    _assign_skill(
        session,
        user_id=senior_id,
        skill_name="Java",
        proficiency=ProficiencyLevel.ADVANCED,
    )
    _assign_skill(
        session,
        user_id=junior_id,
        skill_name="Java",
        proficiency=ProficiencyLevel.BEGINNER,
    )
    filters = TeamSlotFilters(
        skill_name="Java",
        min_proficiency=ProficiencyLevel.INTERMEDIATE,
    )
    service = _service(session)

    results = service.search_candidates(manager_id, filters)

    assert {candidate.user_id for candidate in results} == {senior_id, junior_id}
    best = max(results, key=lambda candidate: service.score_candidate(filters, candidate))
    assert best.user_id == senior_id


def test_search_filters_by_min_free_hours() -> None:
    session = _session()
    manager_id, _project_id = _seed_manager_team(session)
    bench_id = _seed_engineer(
        session,
        manager_user_id=manager_id,
        full_name="Bench Dev",
        email="bench@example.test",
        username="bench.dev",
        utilisation_percent=0,
        work_status=ResourceWorkStatus.BENCH,
    )
    busy_id = _seed_engineer(
        session,
        manager_user_id=manager_id,
        full_name="Busy Dev",
        email="busy@example.test",
        username="busy.dev",
        utilisation_percent=90,
        work_status=ResourceWorkStatus.ALLOCATED,
    )
    for user_id in (bench_id, busy_id):
        _assign_skill(
            session,
            user_id=user_id,
            skill_name="Java",
            proficiency=ProficiencyLevel.ADVANCED,
        )

    results = _service(session).search_candidates(
        manager_id,
        TeamSlotFilters(min_free_hours_per_week=20),
    )

    assert [candidate.user_id for candidate in results] == [bench_id]


def test_search_work_status_is_hard_filter_only_when_set() -> None:
    session = _session()
    manager_id, _project_id = _seed_manager_team(session)
    bench_id = _seed_engineer(
        session,
        manager_user_id=manager_id,
        full_name="Bench Dev",
        email="bench@example.test",
        username="bench.dev",
        utilisation_percent=0,
        work_status=ResourceWorkStatus.BENCH,
    )
    allocated_id = _seed_engineer(
        session,
        manager_user_id=manager_id,
        full_name="Allocated Dev",
        email="allocated@example.test",
        username="allocated.dev",
        utilisation_percent=50,
        work_status=ResourceWorkStatus.ALLOCATED,
    )
    for user_id in (bench_id, allocated_id):
        _assign_skill(
            session,
            user_id=user_id,
            skill_name="Java",
            proficiency=ProficiencyLevel.ADVANCED,
        )

    bench_only = _service(session).search_candidates(
        manager_id,
        TeamSlotFilters(work_status=ResourceWorkStatus.BENCH),
    )
    either_status = _service(session).search_candidates(
        manager_id,
        TeamSlotFilters(),
    )

    assert [candidate.user_id for candidate in bench_only] == [bench_id]
    assert {candidate.user_id for candidate in either_status} == {bench_id, allocated_id}


def test_score_prefers_department_designation_and_activity_tags() -> None:
    session = _session()
    manager_id, _project_id = _seed_manager_team(session)
    match_id = _seed_engineer(
        session,
        manager_user_id=manager_id,
        full_name="Match Dev",
        email="match@example.test",
        username="match.dev",
        utilisation_percent=0,
        work_status=ResourceWorkStatus.BENCH,
        department_name="Engineering",
        designation_name="SSE",
    )
    other_id = _seed_engineer(
        session,
        manager_user_id=manager_id,
        full_name="Other Dev",
        email="other@example.test",
        username="other.dev",
        utilisation_percent=0,
        work_status=ResourceWorkStatus.BENCH,
        department_name="QA",
        designation_name="SE",
    )
    _assign_skill(
        session,
        user_id=match_id,
        skill_name="Java",
        proficiency=ProficiencyLevel.ADVANCED,
    )
    _assign_skill(
        session,
        user_id=other_id,
        skill_name="Java",
        proficiency=ProficiencyLevel.ADVANCED,
    )
    filters = TeamSlotFilters(
        department="Engineering",
        designation="SSE",
        skill_name="Java",
        activity_tags=(ActivityTag.BACKEND_API,),
    )
    service = _service(
        session,
        tags_by_user={match_id: ["BACKEND_API"], other_id: []},
    )
    results = service.search_candidates(manager_id, filters)
    best = max(results, key=lambda candidate: service.score_candidate(filters, candidate))

    assert {candidate.user_id for candidate in results} == {match_id, other_id}
    assert best.user_id == match_id


def test_search_excludes_user_ids_and_other_manager_team() -> None:
    session = _session()
    manager_id, _project_id = _seed_manager_team(session)
    other_manager_id = create_user(
        session,
        full_name="Other Manager",
        username="other.manager",
        email="other@example.test",
        role=Role.MANAGER,
        department_name="Delivery",
        designation_name="Project Manager",
    )
    team_dev = _seed_engineer(
        session,
        manager_user_id=manager_id,
        full_name="Team Dev",
        email="team@example.test",
        username="team.dev",
        utilisation_percent=0,
        work_status=ResourceWorkStatus.BENCH,
    )
    excluded_dev = _seed_engineer(
        session,
        manager_user_id=manager_id,
        full_name="Excluded Dev",
        email="excluded@example.test",
        username="excluded.dev",
        utilisation_percent=0,
        work_status=ResourceWorkStatus.BENCH,
    )
    outsider = _seed_engineer(
        session,
        manager_user_id=other_manager_id,
        full_name="Outsider Dev",
        email="outsider@example.test",
        username="outsider.dev",
        utilisation_percent=0,
        work_status=ResourceWorkStatus.BENCH,
    )
    for user_id in (team_dev, excluded_dev, outsider):
        _assign_skill(
            session,
            user_id=user_id,
            skill_name="Java",
            proficiency=ProficiencyLevel.ADVANCED,
        )

    results = _service(session).search_candidates(
        manager_id,
        TeamSlotFilters(skill_name="Java"),
        exclude_user_ids={excluded_dev},
    )

    assert [candidate.user_id for candidate in results] == [team_dev]


def test_score_prefers_designation_alias_for_software_engineer() -> None:
    session = _session()
    manager_id, _project_id = _seed_manager_team(session)
    engineer_id = _seed_engineer(
        session,
        manager_user_id=manager_id,
        full_name="SE Dev",
        email="se.dev@example.test",
        username="se.dev",
        utilisation_percent=0,
        work_status=ResourceWorkStatus.BENCH,
        designation_name="SE",
    )
    _assign_skill(
        session,
        user_id=engineer_id,
        skill_name="Docker",
        proficiency=ProficiencyLevel.INTERMEDIATE,
        category=SkillCategory.DEVOPS,
    )
    filters = TeamSlotFilters(designation="Software Engineer")
    service = _service(session)
    results = service.search_candidates(manager_id, filters)
    best = max(results, key=lambda candidate: service.score_candidate(filters, candidate))

    assert best.user_id == engineer_id


def test_score_prefers_devops_department_without_profile_skills() -> None:
    session = _session()
    manager_id, _project_id = _seed_manager_team(session)
    devops_id = _seed_engineer(
        session,
        manager_user_id=manager_id,
        full_name="DevOps Bench",
        email="devops@example.test",
        username="devops.bench",
        utilisation_percent=0,
        work_status=ResourceWorkStatus.BENCH,
        department_name="DevOps",
        designation_name="SE",
    )
    backend_id = _seed_engineer(
        session,
        manager_user_id=manager_id,
        full_name="Backend Bench",
        email="backend@example.test",
        username="backend.bench",
        utilisation_percent=0,
        work_status=ResourceWorkStatus.BENCH,
        department_name="Engineering",
        designation_name="SE",
    )
    filters = TeamSlotFilters(
        department="DevOps",
        designation="SE",
        min_free_hours_per_week=20,
    )
    service = _service(session)
    results = service.search_candidates(manager_id, filters)
    best = max(results, key=lambda candidate: service.score_candidate(filters, candidate))

    assert {candidate.user_id for candidate in results} == {devops_id, backend_id}
    assert best.user_id == devops_id


def test_meets_skill_requirements_rejects_below_min_proficiency() -> None:
    session = _session()
    manager_id, _project_id = _seed_manager_team(session)
    junior_id = _seed_engineer(
        session,
        manager_user_id=manager_id,
        full_name="Junior Dev",
        email="junior@example.test",
        username="junior.dev",
        utilisation_percent=0,
        work_status=ResourceWorkStatus.BENCH,
    )
    _assign_skill(
        session,
        user_id=junior_id,
        skill_name="Spring Boot",
        proficiency=ProficiencyLevel.BEGINNER,
    )
    filters = TeamSlotFilters(
        skill_name="Spring Boot",
        min_proficiency=ProficiencyLevel.ADVANCED,
    )
    service = _service(session)
    candidate = service.search_candidates(manager_id, filters)[0]

    assert service.meets_skill_requirements(filters, candidate) is False
