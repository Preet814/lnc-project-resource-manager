"""Unit tests for SQLAlchemy employee-skill repository."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from prm.domain.enums import ProficiencyLevel, Role, SkillCategory
from prm.domain.exceptions import NotFoundError
from prm.infrastructure.db.models import EmployeeModel, EmployeeSkillModel, SkillModel, UserModel
from prm.infrastructure.db.repositories import (
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
    SkillModel.__table__.create(engine, checkfirst=True)
    EmployeeSkillModel.__table__.create(engine, checkfirst=True)
    return Session(engine)


def _seed_employee_and_skill(session: Session) -> tuple[int, int]:
    user_repo = SqlAlchemyUserRepository(session)
    hasher = BcryptPasswordHasher()
    user = user_repo.create(
        full_name="Ravi Kumar",
        username="ravi",
        email="ravi@example.test",
        password_hash=hasher.hash("TempPass1"),
        role=Role.EMPLOYEE,
    )
    employee_repo = SqlAlchemyEmployeeRepository(session)
    employee = employee_repo.create(
        user_id=user.id,
        full_name="Ravi Kumar",
        email="ravi@example.test",
        department="Backend",
        designation="Developer",
    )
    skill_repo = SqlAlchemySkillRepository(session)
    skill = skill_repo.create(name="Java", category=SkillCategory.BACKEND)
    session.flush()
    return employee.id, skill.id


def test_assign_creates_employee_skill_link() -> None:
    with _session() as session:
        employee_id, skill_id = _seed_employee_and_skill(session)
        repo = SqlAlchemyEmployeeSkillRepository(session)

        assigned = repo.assign(
            employee_id=employee_id,
            skill_id=skill_id,
            proficiency=ProficiencyLevel.INTERMEDIATE,
        )
        session.commit()

        assert assigned.employee_id == employee_id
        assert assigned.skill_id == skill_id
        assert assigned.proficiency == ProficiencyLevel.INTERMEDIATE


def test_list_for_employee_returns_assignments_ordered_by_id() -> None:
    with _session() as session:
        employee_id, first_skill_id = _seed_employee_and_skill(session)
        skill_repo = SqlAlchemySkillRepository(session)
        second_skill = skill_repo.create(name="Spring Boot", category=SkillCategory.BACKEND)
        repo = SqlAlchemyEmployeeSkillRepository(session)
        first = repo.assign(
            employee_id=employee_id,
            skill_id=first_skill_id,
            proficiency=ProficiencyLevel.INTERMEDIATE,
        )
        second = repo.assign(
            employee_id=employee_id,
            skill_id=second_skill.id,
            proficiency=ProficiencyLevel.ADVANCED,
        )
        session.commit()

        assignments = repo.list_for_employee(employee_id)

        assert len(assignments) == 2
        assert assignments[0].id == first.id
        assert assignments[1].id == second.id


def test_find_by_employee_and_skill_returns_assignment() -> None:
    with _session() as session:
        employee_id, skill_id = _seed_employee_and_skill(session)
        repo = SqlAlchemyEmployeeSkillRepository(session)
        assigned = repo.assign(
            employee_id=employee_id,
            skill_id=skill_id,
            proficiency=ProficiencyLevel.BEGINNER,
        )
        session.commit()

        loaded = repo.find_by_employee_and_skill(employee_id, skill_id)

        assert loaded is not None
        assert loaded.id == assigned.id


def test_find_by_employee_and_skill_returns_none_when_missing() -> None:
    with _session() as session:
        employee_id, skill_id = _seed_employee_and_skill(session)
        repo = SqlAlchemyEmployeeSkillRepository(session)

        assert repo.find_by_employee_and_skill(employee_id, skill_id) is None


def test_update_proficiency_changes_level() -> None:
    with _session() as session:
        employee_id, skill_id = _seed_employee_and_skill(session)
        repo = SqlAlchemyEmployeeSkillRepository(session)
        assigned = repo.assign(
            employee_id=employee_id,
            skill_id=skill_id,
            proficiency=ProficiencyLevel.BEGINNER,
        )
        session.commit()

        updated = repo.update_proficiency(
            assigned.id,
            proficiency=ProficiencyLevel.ADVANCED,
        )
        session.commit()

        assert updated.proficiency == ProficiencyLevel.ADVANCED


def test_update_proficiency_raises_when_missing() -> None:
    with _session() as session:
        repo = SqlAlchemyEmployeeSkillRepository(session)
        with pytest.raises(NotFoundError):
            repo.update_proficiency(999, proficiency=ProficiencyLevel.ADVANCED)


def test_remove_deletes_assignment() -> None:
    with _session() as session:
        employee_id, skill_id = _seed_employee_and_skill(session)
        repo = SqlAlchemyEmployeeSkillRepository(session)
        assigned = repo.assign(
            employee_id=employee_id,
            skill_id=skill_id,
            proficiency=ProficiencyLevel.INTERMEDIATE,
        )
        session.commit()

        repo.remove(assigned.id)
        session.commit()

        assert repo.list_for_employee(employee_id) == []


def test_remove_raises_when_missing() -> None:
    with _session() as session:
        repo = SqlAlchemyEmployeeSkillRepository(session)
        with pytest.raises(NotFoundError):
            repo.remove(999)
