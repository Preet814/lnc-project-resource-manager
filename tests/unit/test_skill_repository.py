"""Unit tests for SQLAlchemy skill repository."""

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from prm.domain.enums import SkillCategory
from prm.infrastructure.db.models import SkillModel
from prm.infrastructure.db.repositories import SqlAlchemySkillRepository


def _session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    SkillModel.__table__.create(engine, checkfirst=True)
    return Session(engine)


def test_create_persists_skill() -> None:
    with _session() as session:
        repo = SqlAlchemySkillRepository(session)

        created = repo.create(
            name="Java",
            category=SkillCategory.BACKEND,
            is_predefined=True,
        )
        session.commit()

        assert created.name == "Java"
        assert created.category == SkillCategory.BACKEND
        assert created.is_predefined is True


def test_find_by_id_returns_domain_skill() -> None:
    with _session() as session:
        repo = SqlAlchemySkillRepository(session)
        created = repo.create(name="Spring Boot", category=SkillCategory.BACKEND)
        session.commit()

        loaded = repo.find_by_id(created.id)

        assert loaded is not None
        assert loaded.name == "Spring Boot"


def test_find_by_name_returns_domain_skill() -> None:
    with _session() as session:
        repo = SqlAlchemySkillRepository(session)
        repo.create(name="MySQL", category=SkillCategory.BACKEND)
        session.commit()

        loaded = repo.find_by_name("MySQL")

        assert loaded is not None
        assert loaded.category == SkillCategory.BACKEND


def test_find_returns_none_when_missing() -> None:
    with _session() as session:
        repo = SqlAlchemySkillRepository(session)

        assert repo.find_by_id(999) is None
        assert repo.find_by_name("Missing") is None


def test_get_or_create_returns_existing_skill() -> None:
    with _session() as session:
        repo = SqlAlchemySkillRepository(session)
        existing = repo.create(name="WebSocket", category=SkillCategory.BACKEND)
        session.commit()

        loaded = repo.get_or_create(name="WebSocket", category=SkillCategory.FRONTEND)

        assert loaded.id == existing.id
        assert loaded.category == SkillCategory.BACKEND


def test_get_or_create_creates_when_missing() -> None:
    with _session() as session:
        repo = SqlAlchemySkillRepository(session)

        created = repo.get_or_create(name="React", category=SkillCategory.FRONTEND)
        session.commit()

        assert created.id is not None
        assert repo.find_by_name("React") is not None
