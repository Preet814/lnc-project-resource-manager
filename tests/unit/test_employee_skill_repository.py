"""Unit tests for SQLAlchemy user-skill repository."""

import pytest
from sqlalchemy.orm import Session

from prm.domain.enums import ProficiencyLevel, Role, SkillCategory
from prm.domain.exceptions import NotFoundError
from prm.infrastructure.db.repositories import (
    SqlAlchemySkillRepository,
    SqlAlchemyUserSkillRepository,
)
from tests.unit.engineer_fixtures import (
    create_memory_session,
    create_skill_tables,
    create_user,
    seed_rbac,
)


def _session() -> Session:
    session = create_memory_session()
    create_skill_tables(session)
    return session


def _seed_user_and_skill(session: Session) -> tuple[int, int]:
    seed_rbac(session)
    user_id = create_user(
        session,
        username="ravi",
        email="ravi@example.test",
        full_name="Ravi Kumar",
        role=Role.ENGINEER,
    )
    skill_repo = SqlAlchemySkillRepository(session)
    skill = skill_repo.create(name="Java", category=SkillCategory.BACKEND)
    session.flush()
    return user_id, skill.id


def test_assign_creates_user_skill_link() -> None:
    with _session() as session:
        user_id, skill_id = _seed_user_and_skill(session)
        repo = SqlAlchemyUserSkillRepository(session)

        assigned = repo.assign(
            user_id=user_id,
            skill_id=skill_id,
            proficiency=ProficiencyLevel.INTERMEDIATE,
        )
        session.commit()

        assert assigned.user_id == user_id
        assert assigned.skill_id == skill_id
        assert assigned.proficiency == ProficiencyLevel.INTERMEDIATE


def test_list_for_user_returns_assignments_ordered_by_id() -> None:
    with _session() as session:
        user_id, first_skill_id = _seed_user_and_skill(session)
        skill_repo = SqlAlchemySkillRepository(session)
        second_skill = skill_repo.create(name="Spring Boot", category=SkillCategory.BACKEND)
        repo = SqlAlchemyUserSkillRepository(session)
        first = repo.assign(
            user_id=user_id,
            skill_id=first_skill_id,
            proficiency=ProficiencyLevel.INTERMEDIATE,
        )
        second = repo.assign(
            user_id=user_id,
            skill_id=second_skill.id,
            proficiency=ProficiencyLevel.ADVANCED,
        )
        session.commit()

        assignments = repo.list_for_user(user_id)

        assert len(assignments) == 2
        assert assignments[0].id == first.id
        assert assignments[1].id == second.id


def test_find_by_user_and_skill_returns_assignment() -> None:
    with _session() as session:
        user_id, skill_id = _seed_user_and_skill(session)
        repo = SqlAlchemyUserSkillRepository(session)
        assigned = repo.assign(
            user_id=user_id,
            skill_id=skill_id,
            proficiency=ProficiencyLevel.BEGINNER,
        )
        session.commit()

        loaded = repo.find_by_user_and_skill(user_id, skill_id)

        assert loaded is not None
        assert loaded.id == assigned.id


def test_find_by_user_and_skill_returns_none_when_missing() -> None:
    with _session() as session:
        user_id, skill_id = _seed_user_and_skill(session)
        repo = SqlAlchemyUserSkillRepository(session)

        assert repo.find_by_user_and_skill(user_id, skill_id) is None


def test_update_proficiency_changes_level() -> None:
    with _session() as session:
        user_id, skill_id = _seed_user_and_skill(session)
        repo = SqlAlchemyUserSkillRepository(session)
        assigned = repo.assign(
            user_id=user_id,
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
        repo = SqlAlchemyUserSkillRepository(session)
        with pytest.raises(NotFoundError):
            repo.update_proficiency(999, proficiency=ProficiencyLevel.ADVANCED)


def test_remove_deletes_assignment() -> None:
    with _session() as session:
        user_id, skill_id = _seed_user_and_skill(session)
        repo = SqlAlchemyUserSkillRepository(session)
        assigned = repo.assign(
            user_id=user_id,
            skill_id=skill_id,
            proficiency=ProficiencyLevel.INTERMEDIATE,
        )
        session.commit()

        repo.remove(assigned.id)
        session.commit()

        assert repo.list_for_user(user_id) == []


def test_remove_raises_when_missing() -> None:
    with _session() as session:
        repo = SqlAlchemyUserSkillRepository(session)
        with pytest.raises(NotFoundError):
            repo.remove(999)
