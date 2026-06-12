"""Unit tests for UserSkillService."""

import pytest
from sqlalchemy.orm import Session

from prm.application.user_management_service import UserManagementService
from prm.application.user_profile_service import UserProfileService
from prm.application.user_skill_service import UserSkillService
from prm.domain.enums import ProficiencyLevel, Role, SkillCategory
from prm.domain.exceptions import NotFoundError, ValidationError
from prm.infrastructure.db.repositories import (
    SqlAlchemyAllocationRepository,
    SqlAlchemySkillRepository,
    SqlAlchemyUserRepository,
    SqlAlchemyUserSkillRepository,
)
from prm.infrastructure.security.password import BcryptPasswordHasher
from tests.unit.engineer_fixtures import (
    create_allocation_tables,
    create_memory_session,
    create_skill_tables,
    seed_rbac,
)


def _session() -> Session:
    session = create_memory_session(include_project=True)
    create_allocation_tables(session)
    create_skill_tables(session)
    return session


def _user_skill_service(session: Session) -> UserSkillService:
    return UserSkillService(
        user_repository=SqlAlchemyUserRepository(session),
        skill_repository=SqlAlchemySkillRepository(session),
        user_skill_repository=SqlAlchemyUserSkillRepository(session),
    )


def _user_profile_service(session: Session) -> UserProfileService:
    return UserProfileService(
        user_repository=SqlAlchemyUserRepository(session),
        allocation_repository=SqlAlchemyAllocationRepository(session),
    )


def _create_engineer(session: Session) -> int:
    seed_rbac(session)
    user = UserManagementService(
        user_repository=SqlAlchemyUserRepository(session),
        password_hasher=BcryptPasswordHasher(),
    ).create_user(
        full_name="Ravi Kumar",
        email="ravi@example.test",
        username="ravi",
        temporary_password="TempPass1",
        role=Role.ENGINEER,
    )
    session.flush()
    engineer = _user_profile_service(session).create_employee(
        user_id=user.id,
        full_name="Ravi Kumar",
        email="ravi@example.test",
        department="Backend",
        designation="SE",
    )
    session.flush()
    return engineer.id


def test_list_skills_returns_skill_details() -> None:
    with _session() as session:
        user_id = _create_engineer(session)
        service = _user_skill_service(session)
        service.add_skill(
            user_id,
            skill_name="Java",
            category=SkillCategory.BACKEND,
            proficiency=ProficiencyLevel.INTERMEDIATE,
        )
        service.add_skill(
            user_id,
            skill_name="Spring Boot",
            category=SkillCategory.BACKEND,
            proficiency=ProficiencyLevel.ADVANCED,
        )
        session.commit()

        skills = service.list_skills(user_id)

        assert len(skills) == 2
        assert skills[0].skill_name == "Java"
        assert skills[0].proficiency == ProficiencyLevel.INTERMEDIATE
        assert skills[1].skill_name == "Spring Boot"
        assert skills[1].category == SkillCategory.BACKEND


def test_add_skill_creates_catalog_entry_and_assignment() -> None:
    with _session() as session:
        user_id = _create_engineer(session)
        service = _user_skill_service(session)

        added = service.add_skill(
            user_id,
            skill_name="WebSocket",
            category=SkillCategory.BACKEND,
            proficiency=ProficiencyLevel.INTERMEDIATE,
        )
        session.commit()

        assert added.skill_name == "WebSocket"
        assert added.category == SkillCategory.BACKEND
        assert SqlAlchemySkillRepository(session).find_by_name("WebSocket") is not None


def test_add_skill_reuses_existing_catalog_skill() -> None:
    with _session() as session:
        first_user_id = _create_engineer(session)
        second_user = UserManagementService(
            user_repository=SqlAlchemyUserRepository(session),
            password_hasher=BcryptPasswordHasher(),
        ).create_user(
            full_name="Priya Sharma",
            email="priya@example.test",
            username="priya",
            temporary_password="TempPass1",
            role=Role.ENGINEER,
        )
        session.flush()
        second_user_id = _user_profile_service(session).create_employee(
            user_id=second_user.id,
            full_name="Priya Sharma",
            email="priya@example.test",
            department="Frontend",
            designation="SE",
        ).id
        service = _user_skill_service(session)
        first = service.add_skill(
            first_user_id,
            skill_name="Java",
            category=SkillCategory.BACKEND,
            proficiency=ProficiencyLevel.INTERMEDIATE,
        )
        second = service.add_skill(
            second_user_id,
            skill_name="Java",
            category=SkillCategory.FRONTEND,
            proficiency=ProficiencyLevel.BEGINNER,
        )
        session.commit()

        assert first.skill_id == second.skill_id


def test_add_skill_fails_when_name_blank() -> None:
    with _session() as session:
        user_id = _create_engineer(session)
        with pytest.raises(ValidationError, match="Skill name is required"):
            _user_skill_service(session).add_skill(
                user_id,
                skill_name="   ",
                category=SkillCategory.BACKEND,
                proficiency=ProficiencyLevel.BEGINNER,
            )


def test_add_skill_fails_when_duplicate_on_same_employee() -> None:
    with _session() as session:
        user_id = _create_engineer(session)
        service = _user_skill_service(session)
        service.add_skill(
            user_id,
            skill_name="Java",
            category=SkillCategory.BACKEND,
            proficiency=ProficiencyLevel.INTERMEDIATE,
        )
        session.commit()

        with pytest.raises(ValidationError, match="already has skill"):
            service.add_skill(
                user_id,
                skill_name="Java",
                category=SkillCategory.BACKEND,
                proficiency=ProficiencyLevel.ADVANCED,
            )


def test_add_skill_fails_when_employee_missing() -> None:
    with _session() as session:
        with pytest.raises(NotFoundError):
            _user_skill_service(session).add_skill(
                999,
                skill_name="Java",
                category=SkillCategory.BACKEND,
                proficiency=ProficiencyLevel.BEGINNER,
            )


def test_add_skill_fails_when_employee_inactive() -> None:
    with _session() as session:
        user_id = _create_engineer(session)
        _user_profile_service(session).deactivate_employee(user_id)
        session.commit()

        with pytest.raises(ValidationError, match="inactive"):
            _user_skill_service(session).add_skill(
                user_id,
                skill_name="Java",
                category=SkillCategory.BACKEND,
                proficiency=ProficiencyLevel.BEGINNER,
            )


def test_update_proficiency_changes_level() -> None:
    with _session() as session:
        user_id = _create_engineer(session)
        service = _user_skill_service(session)
        added = service.add_skill(
            user_id,
            skill_name="Java",
            category=SkillCategory.BACKEND,
            proficiency=ProficiencyLevel.BEGINNER,
        )
        session.commit()

        updated = service.update_proficiency(
            user_id,
            added.user_skill_id,
            proficiency=ProficiencyLevel.ADVANCED,
        )
        session.commit()

        assert updated.proficiency == ProficiencyLevel.ADVANCED


def test_update_proficiency_fails_when_assignment_not_for_employee() -> None:
    with _session() as session:
        first_user_id = _create_engineer(session)
        second_user = UserManagementService(
            user_repository=SqlAlchemyUserRepository(session),
            password_hasher=BcryptPasswordHasher(),
        ).create_user(
            full_name="Priya Sharma",
            email="priya@example.test",
            username="priya",
            temporary_password="TempPass1",
            role=Role.ENGINEER,
        )
        session.flush()
        second_user_id = _user_profile_service(session).create_employee(
            user_id=second_user.id,
            full_name="Priya Sharma",
            email="priya@example.test",
            department="Frontend",
            designation="SE",
        ).id
        service = _user_skill_service(session)
        added = service.add_skill(
            first_user_id,
            skill_name="Java",
            category=SkillCategory.BACKEND,
            proficiency=ProficiencyLevel.BEGINNER,
        )
        session.commit()

        with pytest.raises(NotFoundError):
            service.update_proficiency(
                second_user_id,
                added.user_skill_id,
                proficiency=ProficiencyLevel.ADVANCED,
            )


def test_remove_skill_deletes_assignment() -> None:
    with _session() as session:
        user_id = _create_engineer(session)
        service = _user_skill_service(session)
        added = service.add_skill(
            user_id,
            skill_name="Java",
            category=SkillCategory.BACKEND,
            proficiency=ProficiencyLevel.INTERMEDIATE,
        )
        session.commit()

        service.remove_skill(user_id, added.user_skill_id)
        session.commit()

        assert service.list_skills(user_id) == ()


def test_remove_skill_fails_when_assignment_not_for_employee() -> None:
    with _session() as session:
        first_user_id = _create_engineer(session)
        second_user = UserManagementService(
            user_repository=SqlAlchemyUserRepository(session),
            password_hasher=BcryptPasswordHasher(),
        ).create_user(
            full_name="Priya Sharma",
            email="priya@example.test",
            username="priya",
            temporary_password="TempPass1",
            role=Role.ENGINEER,
        )
        session.flush()
        second_user_id = _user_profile_service(session).create_employee(
            user_id=second_user.id,
            full_name="Priya Sharma",
            email="priya@example.test",
            department="Frontend",
            designation="SE",
        ).id
        service = _user_skill_service(session)
        added = service.add_skill(
            first_user_id,
            skill_name="Java",
            category=SkillCategory.BACKEND,
            proficiency=ProficiencyLevel.INTERMEDIATE,
        )
        session.commit()

        with pytest.raises(NotFoundError):
            service.remove_skill(second_user_id, added.user_skill_id)
