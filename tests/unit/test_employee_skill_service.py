"""Unit tests for EmployeeSkillService."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from prm.application.employee_management_service import EmployeeManagementService
from prm.application.employee_skill_service import EmployeeSkillService
from prm.application.user_management_service import UserManagementService
from prm.domain.enums import ProficiencyLevel, Role, SkillCategory
from prm.domain.exceptions import NotFoundError, ValidationError
from prm.infrastructure.db.models import (
    AllocationModel,
    EmployeeModel,
    EmployeeSkillModel,
    ProjectModel,
    SkillModel,
    UserModel,
)
from prm.infrastructure.db.repositories import (
    SqlAlchemyAllocationRepository,
    SqlAlchemyEmployeeRepository,
    SqlAlchemyEmployeeSkillRepository,
    SqlAlchemySkillRepository,
    SqlAlchemyUserRepository,
)
from prm.infrastructure.security.password import BcryptPasswordHasher


def _session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    UserModel.__table__.create(engine, checkfirst=True)
    EmployeeModel.__table__.create(engine, checkfirst=True)
    ProjectModel.__table__.create(engine, checkfirst=True)
    AllocationModel.__table__.create(engine, checkfirst=True)
    SkillModel.__table__.create(engine, checkfirst=True)
    EmployeeSkillModel.__table__.create(engine, checkfirst=True)
    return Session(engine)


def _employee_skill_service(session: Session) -> EmployeeSkillService:
    return EmployeeSkillService(
        employee_repository=SqlAlchemyEmployeeRepository(session),
        skill_repository=SqlAlchemySkillRepository(session),
        employee_skill_repository=SqlAlchemyEmployeeSkillRepository(session),
    )


def _employee_management_service(session: Session) -> EmployeeManagementService:
    return EmployeeManagementService(
        employee_repository=SqlAlchemyEmployeeRepository(session),
        user_repository=SqlAlchemyUserRepository(session),
        allocation_repository=SqlAlchemyAllocationRepository(session),
    )


def _create_employee(session: Session) -> int:
    user = UserManagementService(
        user_repository=SqlAlchemyUserRepository(session),
        password_hasher=BcryptPasswordHasher(),
    ).create_user(
        full_name="Ravi Kumar",
        email="ravi@example.test",
        username="ravi",
        temporary_password="TempPass1",
        role=Role.EMPLOYEE,
    )
    session.flush()
    employee = _employee_management_service(session).create_employee(
        user_id=user.id,
        full_name="Ravi Kumar",
        email="ravi@example.test",
        department="Backend",
        designation="Developer",
    )
    session.flush()
    return employee.id


def test_list_skills_returns_skill_details() -> None:
    with _session() as session:
        employee_id = _create_employee(session)
        service = _employee_skill_service(session)
        service.add_skill(
            employee_id,
            skill_name="Java",
            category=SkillCategory.BACKEND,
            proficiency=ProficiencyLevel.INTERMEDIATE,
        )
        service.add_skill(
            employee_id,
            skill_name="Spring Boot",
            category=SkillCategory.BACKEND,
            proficiency=ProficiencyLevel.ADVANCED,
        )
        session.commit()

        skills = service.list_skills(employee_id)

        assert len(skills) == 2
        assert skills[0].skill_name == "Java"
        assert skills[0].proficiency == ProficiencyLevel.INTERMEDIATE
        assert skills[1].skill_name == "Spring Boot"
        assert skills[1].category == SkillCategory.BACKEND


def test_add_skill_creates_catalog_entry_and_assignment() -> None:
    with _session() as session:
        employee_id = _create_employee(session)
        service = _employee_skill_service(session)

        added = service.add_skill(
            employee_id,
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
        first_employee = _create_employee(session)
        second_user = UserManagementService(
            user_repository=SqlAlchemyUserRepository(session),
            password_hasher=BcryptPasswordHasher(),
        ).create_user(
            full_name="Priya Sharma",
            email="priya@example.test",
            username="priya",
            temporary_password="TempPass1",
            role=Role.EMPLOYEE,
        )
        session.flush()
        second_employee = _employee_management_service(session).create_employee(
            user_id=second_user.id,
            full_name="Priya Sharma",
            email="priya@example.test",
            department="Frontend",
            designation="Developer",
        )
        service = _employee_skill_service(session)
        first = service.add_skill(
            first_employee,
            skill_name="Java",
            category=SkillCategory.BACKEND,
            proficiency=ProficiencyLevel.INTERMEDIATE,
        )
        second = service.add_skill(
            second_employee.id,
            skill_name="Java",
            category=SkillCategory.FRONTEND,
            proficiency=ProficiencyLevel.BEGINNER,
        )
        session.commit()

        assert first.skill_id == second.skill_id


def test_add_skill_fails_when_name_blank() -> None:
    with _session() as session:
        employee_id = _create_employee(session)
        with pytest.raises(ValidationError, match="Skill name is required"):
            _employee_skill_service(session).add_skill(
                employee_id,
                skill_name="   ",
                category=SkillCategory.BACKEND,
                proficiency=ProficiencyLevel.BEGINNER,
            )


def test_add_skill_fails_when_duplicate_on_same_employee() -> None:
    with _session() as session:
        employee_id = _create_employee(session)
        service = _employee_skill_service(session)
        service.add_skill(
            employee_id,
            skill_name="Java",
            category=SkillCategory.BACKEND,
            proficiency=ProficiencyLevel.INTERMEDIATE,
        )
        session.commit()

        with pytest.raises(ValidationError, match="already has skill"):
            service.add_skill(
                employee_id,
                skill_name="Java",
                category=SkillCategory.BACKEND,
                proficiency=ProficiencyLevel.ADVANCED,
            )


def test_add_skill_fails_when_employee_missing() -> None:
    with _session() as session:
        with pytest.raises(NotFoundError):
            _employee_skill_service(session).add_skill(
                999,
                skill_name="Java",
                category=SkillCategory.BACKEND,
                proficiency=ProficiencyLevel.BEGINNER,
            )


def test_add_skill_fails_when_employee_inactive() -> None:
    with _session() as session:
        employee_id = _create_employee(session)
        _employee_management_service(session).deactivate_employee(employee_id)
        session.commit()

        with pytest.raises(ValidationError, match="inactive"):
            _employee_skill_service(session).add_skill(
                employee_id,
                skill_name="Java",
                category=SkillCategory.BACKEND,
                proficiency=ProficiencyLevel.BEGINNER,
            )


def test_update_proficiency_changes_level() -> None:
    with _session() as session:
        employee_id = _create_employee(session)
        service = _employee_skill_service(session)
        added = service.add_skill(
            employee_id,
            skill_name="Java",
            category=SkillCategory.BACKEND,
            proficiency=ProficiencyLevel.BEGINNER,
        )
        session.commit()

        updated = service.update_proficiency(
            employee_id,
            added.employee_skill_id,
            proficiency=ProficiencyLevel.ADVANCED,
        )
        session.commit()

        assert updated.proficiency == ProficiencyLevel.ADVANCED


def test_update_proficiency_fails_when_assignment_not_for_employee() -> None:
    with _session() as session:
        first_employee = _create_employee(session)
        second_user = UserManagementService(
            user_repository=SqlAlchemyUserRepository(session),
            password_hasher=BcryptPasswordHasher(),
        ).create_user(
            full_name="Priya Sharma",
            email="priya@example.test",
            username="priya",
            temporary_password="TempPass1",
            role=Role.EMPLOYEE,
        )
        session.flush()
        second_employee = _employee_management_service(session).create_employee(
            user_id=second_user.id,
            full_name="Priya Sharma",
            email="priya@example.test",
            department="Frontend",
            designation="Developer",
        )
        service = _employee_skill_service(session)
        added = service.add_skill(
            first_employee,
            skill_name="Java",
            category=SkillCategory.BACKEND,
            proficiency=ProficiencyLevel.BEGINNER,
        )
        session.commit()

        with pytest.raises(NotFoundError):
            service.update_proficiency(
                second_employee.id,
                added.employee_skill_id,
                proficiency=ProficiencyLevel.ADVANCED,
            )


def test_remove_skill_deletes_assignment() -> None:
    with _session() as session:
        employee_id = _create_employee(session)
        service = _employee_skill_service(session)
        added = service.add_skill(
            employee_id,
            skill_name="Java",
            category=SkillCategory.BACKEND,
            proficiency=ProficiencyLevel.INTERMEDIATE,
        )
        session.commit()

        service.remove_skill(employee_id, added.employee_skill_id)
        session.commit()

        assert service.list_skills(employee_id) == ()


def test_remove_skill_fails_when_assignment_not_for_employee() -> None:
    with _session() as session:
        first_employee = _create_employee(session)
        second_user = UserManagementService(
            user_repository=SqlAlchemyUserRepository(session),
            password_hasher=BcryptPasswordHasher(),
        ).create_user(
            full_name="Priya Sharma",
            email="priya@example.test",
            username="priya",
            temporary_password="TempPass1",
            role=Role.EMPLOYEE,
        )
        session.flush()
        second_employee = _employee_management_service(session).create_employee(
            user_id=second_user.id,
            full_name="Priya Sharma",
            email="priya@example.test",
            department="Frontend",
            designation="Developer",
        )
        service = _employee_skill_service(session)
        added = service.add_skill(
            first_employee,
            skill_name="Java",
            category=SkillCategory.BACKEND,
            proficiency=ProficiencyLevel.INTERMEDIATE,
        )
        session.commit()

        with pytest.raises(NotFoundError):
            service.remove_skill(second_employee.id, added.employee_skill_id)
