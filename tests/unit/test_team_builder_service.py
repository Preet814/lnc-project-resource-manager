"""Unit tests for TeamBuilderService."""

from datetime import date

import pytest
from sqlalchemy.orm import Session

from prm.application.authorization_service import AuthorizationService
from prm.application.team_builder_service import TeamBuilderService
from prm.domain.dtos import TeamRoleRequirement, TeamRoleSkillRequirement
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


def _session() -> Session:
    session = create_memory_session(include_project=True)
    create_skill_tables(session)
    create_allocation_tables(session)
    return session


def _service(session: Session, *, max_weekly_hours: int = 40) -> TeamBuilderService:
    project_repo = SqlAlchemyProjectRepository(session)
    return TeamBuilderService(
        user_repository=SqlAlchemyUserRepository(session),
        user_skill_repository=SqlAlchemyUserSkillRepository(session),
        skill_repository=SqlAlchemySkillRepository(session),
        allocation_repository=SqlAlchemyAllocationRepository(session),
        project_repository=project_repo,
        authorization=AuthorizationService(project_repo),
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
    project = SqlAlchemyProjectRepository(session).create(
        name="Banking Portal",
        description="New banking portal",
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


def _banking_team_roles() -> tuple[TeamRoleRequirement, ...]:
    return (
        TeamRoleRequirement(
            role_label="Senior Java Developer",
            required_skills=(
                TeamRoleSkillRequirement("Java", ProficiencyLevel.ADVANCED),
            ),
        ),
        TeamRoleRequirement(
            role_label="DevOps Engineer",
            required_skills=(
                TeamRoleSkillRequirement("Docker", ProficiencyLevel.INTERMEDIATE),
            ),
        ),
        TeamRoleRequirement(
            role_label="QA Tester",
            required_skills=(
                TeamRoleSkillRequirement("Manual Testing", ProficiencyLevel.INTERMEDIATE),
            ),
        ),
    )


def test_build_team_assigns_three_distinct_roles_in_one_pass() -> None:
    session = _session()
    manager_id, project_id = _seed_manager_and_project(session)
    java_dev = _seed_engineer(
        session,
        manager_user_id=manager_id,
        full_name="Ravi Kumar",
        email="ravi@example.test",
        username="ravi.kumar",
        utilisation_percent=0,
    )
    devops = _seed_engineer(
        session,
        manager_user_id=manager_id,
        full_name="Karan Patel",
        email="karan@example.test",
        username="karan.patel",
        utilisation_percent=25,
    )
    qa = _seed_engineer(
        session,
        manager_user_id=manager_id,
        full_name="Divya Nair",
        email="divya@example.test",
        username="divya.nair",
        utilisation_percent=0,
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
    _assign_skill(
        session,
        user_id=qa,
        skill_name="Manual Testing",
        proficiency=ProficiencyLevel.ADVANCED,
        category=SkillCategory.QA,
    )

    result = _service(session).build_team(manager_id, project_id, _banking_team_roles())

    assert len(result.assignments) == 3
    assert len(result.gaps) == 0
    assigned_ids = {assignment.user_id for assignment in result.assignments}
    assert len(assigned_ids) == 3
    assert {assignment.role_label for assignment in result.assignments} == {
        "Senior Java Developer",
        "DevOps Engineer",
        "QA Tester",
    }


def test_build_team_does_not_assign_same_person_to_two_roles() -> None:
    session = _session()
    manager_id, project_id = _seed_manager_and_project(session)
    star = _seed_engineer(
        session,
        manager_user_id=manager_id,
        full_name="Star Dev",
        email="star@example.test",
        username="star.dev",
        utilisation_percent=0,
    )
    backup = _seed_engineer(
        session,
        manager_user_id=manager_id,
        full_name="Backup Dev",
        email="backup@example.test",
        username="backup.dev",
        utilisation_percent=0,
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

    roles = (
        TeamRoleRequirement(
            role_label="Java Lead",
            required_skills=(
                TeamRoleSkillRequirement("Java", ProficiencyLevel.ADVANCED),
            ),
        ),
        TeamRoleRequirement(
            role_label="Spring Developer",
            required_skills=(
                TeamRoleSkillRequirement("Spring", ProficiencyLevel.INTERMEDIATE),
            ),
        ),
    )

    result = _service(session).build_team(manager_id, project_id, roles)

    assert len(result.assignments) == 2
    assigned_ids = [assignment.user_id for assignment in result.assignments]
    assert len(set(assigned_ids)) == 2
    assert star in assigned_ids
    assert backup in assigned_ids


def test_build_team_reports_skill_gap_when_no_one_has_skill() -> None:
    session = _session()
    manager_id, project_id = _seed_manager_and_project(session)
    _seed_engineer(
        session,
        manager_user_id=manager_id,
        full_name="Generalist",
        email="gen@example.test",
        username="gen.dev",
        utilisation_percent=0,
    )
    roles = (
        TeamRoleRequirement(
            role_label="Selenium QA",
            required_skills=(
                TeamRoleSkillRequirement("Selenium", ProficiencyLevel.INTERMEDIATE),
            ),
        ),
    )

    result = _service(session).build_team(manager_id, project_id, roles)

    assert result.assignments == ()
    assert len(result.gaps) == 1
    gap = result.gaps[0]
    assert gap.gap_type == TeamGapType.SKILL_GAP
    assert "Selenium" in gap.detail
    assert gap.availability_hints == ()


def test_build_team_reports_availability_gap_for_insufficient_hours() -> None:
    session = _session()
    manager_id, project_id = _seed_manager_and_project(session)
    busy = _seed_engineer(
        session,
        manager_user_id=manager_id,
        full_name="Busy QA",
        email="busy@example.test",
        username="busy.qa",
        utilisation_percent=90,
        work_status=ResourceWorkStatus.ALLOCATED,
    )
    _assign_skill(
        session,
        user_id=busy,
        skill_name="Manual Testing",
        proficiency=ProficiencyLevel.ADVANCED,
        category=SkillCategory.QA,
    )
    roles = (
        TeamRoleRequirement(
            role_label="QA Tester",
            required_skills=(
                TeamRoleSkillRequirement("Manual Testing", ProficiencyLevel.INTERMEDIATE),
            ),
            hours_per_week=20,
        ),
    )

    result = _service(session).build_team(manager_id, project_id, roles)

    assert result.assignments == ()
    assert len(result.gaps) == 1
    gap = result.gaps[0]
    assert gap.gap_type == TeamGapType.AVAILABILITY_GAP
    assert "Busy QA" in gap.detail
    assert "20" in gap.detail
    assert len(gap.availability_hints) == 1


def test_build_team_reports_availability_gap_with_allocation_end_date() -> None:
    session = _session()
    manager_id, project_id = _seed_manager_and_project(session)
    other_project = SqlAlchemyProjectRepository(session).create(
        name="Beta CRM",
        description="CRM rollout",
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
    roles = (
        TeamRoleRequirement(
            role_label="QA Tester",
            required_skills=(
                TeamRoleSkillRequirement("Manual Testing", ProficiencyLevel.INTERMEDIATE),
            ),
            hours_per_week=25,
        ),
    )

    result = _service(session).build_team(manager_id, project_id, roles)

    assert result.assignments == ()
    gap = result.gaps[0]
    assert gap.gap_type == TeamGapType.AVAILABILITY_GAP
    assert "Beta CRM" in gap.detail
    assert "2026-07-15" in gap.detail
    assert gap.availability_hints[0].available_from == date(2026, 7, 15)


def test_build_team_rejects_empty_roles() -> None:
    session = _session()
    manager_id, project_id = _seed_manager_and_project(session)

    with pytest.raises(ValidationError, match="At least one role"):
        _service(session).build_team(manager_id, project_id, ())


def test_build_team_rejects_non_allocatable_project() -> None:
    session = _session()
    manager_id, _project_id = _seed_manager_and_project(session)
    completed = SqlAlchemyProjectRepository(session).create(
        name="Finished Portal",
        description="Delivered",
        start_date=date(2026, 1, 1),
        end_date=date(2026, 6, 30),
        status=ProjectStatus.COMPLETED,
        manager_user_id=manager_id,
    )

    with pytest.raises(ValidationError, match="ACTIVE or PLANNED"):
        _service(session).build_team(manager_id, completed.id, _banking_team_roles())


def test_build_team_requires_project_owner() -> None:
    session = _session()
    manager_id, _project_id = _seed_manager_and_project(session)
    other_manager_id = create_user(
        session,
        full_name="Other Manager",
        username="other.manager",
        email="other@example.test",
        role=Role.MANAGER,
    )
    other_project = SqlAlchemyProjectRepository(session).create(
        name="Other Project",
        description="Not yours",
        start_date=date(2026, 4, 1),
        end_date=date(2026, 8, 15),
        status=ProjectStatus.ACTIVE,
        manager_user_id=other_manager_id,
    )

    with pytest.raises(UnauthorizedError, match="project owner"):
        _service(session).build_team(manager_id, other_project.id, _banking_team_roles())
