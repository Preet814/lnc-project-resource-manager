"""Unit tests for SQLAlchemy system configuration repository."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from prm.domain.constants import DEFAULT_MAX_WEEKLY_HOURS, DEFAULT_SCHEDULER_INTERVAL_HOURS
from prm.domain.enums import LLMProvider
from prm.domain.exceptions import NotFoundError
from prm.infrastructure.db.models import SystemConfigurationModel
from prm.infrastructure.db.repositories import SqlAlchemySystemConfigurationRepository


def _session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    SystemConfigurationModel.__table__.create(engine, checkfirst=True)
    return Session(engine)


def test_find_singleton_returns_none_when_missing() -> None:
    with _session() as session:
        repo = SqlAlchemySystemConfigurationRepository(session)

        assert repo.find_singleton() is None


def test_create_with_defaults_persists_brd_defaults() -> None:
    with _session() as session:
        repo = SqlAlchemySystemConfigurationRepository(session)

        created = repo.create_with_defaults()
        session.commit()

        assert created.id is not None
        assert created.llm_provider == LLMProvider.GEMINI
        assert created.llm_api_key_encrypted is None
        assert created.scheduler_interval_hours == DEFAULT_SCHEDULER_INTERVAL_HOURS
        assert created.max_weekly_hours == DEFAULT_MAX_WEEKLY_HOURS


def test_find_singleton_returns_existing_row() -> None:
    with _session() as session:
        repo = SqlAlchemySystemConfigurationRepository(session)
        created = repo.create_with_defaults()
        session.commit()

        loaded = repo.find_singleton()

        assert loaded is not None
        assert loaded.id == created.id
        assert loaded.llm_provider == LLMProvider.GEMINI


def test_update_changes_requested_fields_only() -> None:
    with _session() as session:
        repo = SqlAlchemySystemConfigurationRepository(session)
        created = repo.create_with_defaults()
        session.commit()

        updated = repo.update(
            created.id,
            llm_provider=LLMProvider.GROQ,
            scheduler_interval_hours=6,
            max_weekly_hours=35,
        )
        session.commit()

        assert updated.llm_provider == LLMProvider.GROQ
        assert updated.scheduler_interval_hours == 6
        assert updated.max_weekly_hours == 35
        assert updated.llm_api_key_encrypted is None


def test_update_can_set_llm_api_key_encrypted() -> None:
    with _session() as session:
        repo = SqlAlchemySystemConfigurationRepository(session)
        created = repo.create_with_defaults()
        session.commit()

        updated = repo.update(created.id, llm_api_key_encrypted="encrypted-secret")
        session.commit()

        assert updated.llm_api_key_encrypted == "encrypted-secret"


def test_update_raises_when_config_missing() -> None:
    with _session() as session:
        repo = SqlAlchemySystemConfigurationRepository(session)

        with pytest.raises(NotFoundError, match="System configuration 99 not found"):
            repo.update(99, llm_provider=LLMProvider.GROQ)
