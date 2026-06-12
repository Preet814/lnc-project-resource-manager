"""Unit tests for TeamAssignmentService."""

from datetime import date

import pytest
from sqlalchemy.orm import Session

from prm.application.authorization_service import AuthorizationService
from prm.application.team_assignment_service import TeamAssignmentService
from prm.application.team_candidate_search_service import TeamCandidateSearchService
from prm.domain.dtos import TeamPlan, TeamSlotFilters, TeamSlotSpec
from prm.domain.enums import (
    ProficiencyLevel,
    ProjectStatus,
    ResourceWorkStatus,
    Role,
    SkillCategory,
    TeamGapType,
)
from prm.domain.exceptions import UnauthorizedError, ValidationError
from prm.infrastructure.db.models import AllocationModel
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


def _assignment_service(session: Session) -> TeamAssignmentService:
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
    return TeamAssignmentService(
        search_service=search,
        authorization=AuthorizationService(project_repo),
        max_weekly_hours=40,
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


def _seed_engineer(
    session: Session,
    *,
    manager_user_id: int,
    full_name: str,
    email: str,
    username: str,
    utilisation_percent: int,
    work_status: ResourceWorkStatus,
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
            TeamSlotSpec(
                slot_id=2,
                role_label="DevOps Engineer",
                headcount=1,
                filters=TeamSlotFilters(
                    skill_category=SkillCategory.DEVOPS,
                    skill_name="Docker",
                    min_proficiency=ProficiencyLevel.INTERMEDIATE,
                ),
            ),
        ),
    )


def test_assign_team_fills_three_distinct_roles() -> None:
    session = _session()
    manager_id, project_id = _seed_manager_project(session)
    java_dev = _seed_engineer(
        session,
        manager_user_id=manager_id,
        full_name="Ravi Kumar",
        email="ravi@example.test",
        username="ravi.kumar",
        utilisation_percent=0,
        work_status=ResourceWorkStatus.BENCH,
    )
    devops = _seed_engineer(
        session,
        manager_user_id=manager_id,
        full_name="Karan Patel",
        email="karan@example.test",
        username="karan.patel",
        utilisation_percent=25,
        work_status=ResourceWorkStatus.ALLOCATED,
    )
    _assign_skill(
        session,
        user_id=java_dev,
        skill_name="Java",
        proficiency=ProficiencyLevel.ADVANCED,
    )
    _assign_skill(
        session,
        user_id=devops,
        skill_name="Docker",
        proficiency=ProficiencyLevel.ADVANCED,
        category=SkillCategory.DEVOPS,
    )

    result = _assignment_service(session).assign_team(
        manager_id,
        project_id,
        _banking_plan(),
    )

    assert len(result.assignments) == 2
    assert result.gaps == ()
    assert {assignment.user_id for assignment in result.assignments} == {java_dev, devops}


def test_assign_team_prefers_bench_when_work_status_not_required() -> None:
    session = _session()
    manager_id, project_id = _seed_manager_project(session)
    bench = _seed_engineer(
        session,
        manager_user_id=manager_id,
        full_name="Bench Dev",
        email="bench@example.test",
        username="bench.dev",
        utilisation_percent=0,
        work_status=ResourceWorkStatus.BENCH,
    )
    allocated = _seed_engineer(
        session,
        manager_user_id=manager_id,
        full_name="Allocated Dev",
        email="allocated@example.test",
        username="allocated.dev",
        utilisation_percent=25,
        work_status=ResourceWorkStatus.ALLOCATED,
    )
    for user_id in (bench, allocated):
        _assign_skill(
            session,
            user_id=user_id,
            skill_name="Java",
            proficiency=ProficiencyLevel.ADVANCED,
        )

    plan = TeamPlan(
        team_slots=(
            TeamSlotSpec(
                slot_id=1,
                role_label="Java Developer",
                headcount=1,
                filters=TeamSlotFilters(
                    skill_name="Java",
                    min_proficiency=ProficiencyLevel.ADVANCED,
                ),
            ),
        ),
    )
    result = _assignment_service(session).assign_team(manager_id, project_id, plan)

    assert result.assignments[0].user_id == bench


def test_assign_team_does_not_assign_same_person_twice() -> None:
    session = _session()
    manager_id, project_id = _seed_manager_project(session)
    star = _seed_engineer(
        session,
        manager_user_id=manager_id,
        full_name="Star Dev",
        email="star@example.test",
        username="star.dev",
        utilisation_percent=0,
        work_status=ResourceWorkStatus.BENCH,
    )
    backup = _seed_engineer(
        session,
        manager_user_id=manager_id,
        full_name="Backup Dev",
        email="backup@example.test",
        username="backup.dev",
        utilisation_percent=0,
        work_status=ResourceWorkStatus.BENCH,
    )
    _assign_skill(
        session,
        user_id=star,
        skill_name="Java",
        proficiency=ProficiencyLevel.ADVANCED,
    )
    _assign_skill(
        session,
        user_id=star,
        skill_name="Spring",
        proficiency=ProficiencyLevel.ADVANCED,
    )
    _assign_skill(
        session,
        user_id=backup,
        skill_name="Spring",
        proficiency=ProficiencyLevel.INTERMEDIATE,
    )

    plan = TeamPlan(
        team_slots=(
            TeamSlotSpec(
                slot_id=1,
                role_label="Java Lead",
                headcount=1,
                filters=TeamSlotFilters(
                    skill_name="Java",
                    min_proficiency=ProficiencyLevel.ADVANCED,
                ),
            ),
            TeamSlotSpec(
                slot_id=2,
                role_label="Spring Developer",
                headcount=1,
                filters=TeamSlotFilters(
                    skill_name="Spring",
                    min_proficiency=ProficiencyLevel.INTERMEDIATE,
                ),
            ),
        ),
    )
    result = _assignment_service(session).assign_team(manager_id, project_id, plan)

    assert len(result.assignments) == 2
    assert len({assignment.user_id for assignment in result.assignments}) == 2


def test_assign_team_reports_skill_gap() -> None:
    session = _session()
    manager_id, project_id = _seed_manager_project(session)
    plan = TeamPlan(
        team_slots=(
            TeamSlotSpec(
                slot_id=1,
                role_label="Selenium QA",
                headcount=1,
                filters=TeamSlotFilters(
                    skill_name="Selenium",
                    min_proficiency=ProficiencyLevel.INTERMEDIATE,
                ),
            ),
        ),
    )

    result = _assignment_service(session).assign_team(manager_id, project_id, plan)

    assert result.assignments == ()
    assert len(result.gaps) == 1
    assert result.gaps[0].gap_type == TeamGapType.SKILL_GAP
    assert "Selenium" in result.gaps[0].detail


def test_assign_team_reports_availability_gap_with_allocation_end_date() -> None:
    session = _session()
    manager_id, project_id = _seed_manager_project(session)
    other_project = SqlAlchemyProjectRepository(session).create(
        name="Beta CRM",
        description="CRM",
        start_date=date(2026, 1, 1),
        end_date=date(2026, 12, 31),
        status=ProjectStatus.ACTIVE,
        manager_user_id=manager_id,
    )
    engineer_id = _seed_engineer(
        session,
        manager_user_id=manager_id,
        full_name="Ananya Das",
        email="ananya@example.test",
        username="ananya.das",
        utilisation_percent=75,
        work_status=ResourceWorkStatus.ALLOCATED,
    )
    _assign_skill(
        session,
        user_id=engineer_id,
        skill_name="Manual Testing",
        proficiency=ProficiencyLevel.ADVANCED,
        category=SkillCategory.QA,
    )
    session.add(
        AllocationModel(
            user_id=engineer_id,
            project_id=other_project.id,
            utilisation_percent=75,
            from_date=date(2026, 3, 1),
            to_date=date(2026, 7, 15),
            created_by_user_id=manager_id,
        )
    )
    session.commit()
    plan = TeamPlan(
        team_slots=(
            TeamSlotSpec(
                slot_id=1,
                role_label="QA Tester",
                headcount=1,
                filters=TeamSlotFilters(
                    skill_name="Manual Testing",
                    min_proficiency=ProficiencyLevel.INTERMEDIATE,
                    min_free_hours_per_week=25,
                ),
            ),
        ),
    )

    result = _assignment_service(session).assign_team(manager_id, project_id, plan)

    assert result.assignments == ()
    gap = result.gaps[0]
    assert gap.gap_type == TeamGapType.AVAILABILITY_GAP
    assert "Beta CRM" in gap.detail
    assert gap.availability_hints[0].available_from == date(2026, 7, 15)


def test_assign_team_supports_headcount_two() -> None:
    session = _session()
    manager_id, project_id = _seed_manager_project(session)
    first = _seed_engineer(
        session,
        manager_user_id=manager_id,
        full_name="Dev One",
        email="dev1@example.test",
        username="dev.one",
        utilisation_percent=0,
        work_status=ResourceWorkStatus.BENCH,
    )
    second = _seed_engineer(
        session,
        manager_user_id=manager_id,
        full_name="Dev Two",
        email="dev2@example.test",
        username="dev.two",
        utilisation_percent=0,
        work_status=ResourceWorkStatus.BENCH,
    )
    for user_id in (first, second):
        _assign_skill(
            session,
            user_id=user_id,
            skill_name="Java",
            proficiency=ProficiencyLevel.ADVANCED,
        )

    plan = TeamPlan(
        team_slots=(
            TeamSlotSpec(
                slot_id=1,
                role_label="Backend Developer",
                headcount=2,
                filters=TeamSlotFilters(
                    skill_name="Java",
                    min_proficiency=ProficiencyLevel.ADVANCED,
                ),
            ),
        ),
    )
    result = _assignment_service(session).assign_team(manager_id, project_id, plan)

    assert len(result.assignments) == 2
    assert len({assignment.user_id for assignment in result.assignments}) == 2


def test_assign_team_requires_project_owner() -> None:
    session = _session()
    manager_id, project_id = _seed_manager_project(session)
    other_manager_id = create_user(
        session,
        full_name="Other Manager",
        username="other.manager",
        email="other@example.test",
        role=Role.MANAGER,
    )

    with pytest.raises(UnauthorizedError, match="project owner"):
        _assignment_service(session).assign_team(
            other_manager_id,
            project_id,
            _banking_plan(),
        )


def test_assign_team_rejects_empty_plan() -> None:
    session = _session()
    manager_id, project_id = _seed_manager_project(session)

    with pytest.raises(ValidationError, match="at least one slot"):
        _assignment_service(session).assign_team(
            manager_id,
            project_id,
            TeamPlan(team_slots=()),
        )
