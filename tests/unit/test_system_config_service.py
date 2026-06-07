"""Unit tests for SystemConfigService."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from prm.application.system_config_service import SystemConfigService
from prm.domain.constants import (
    DEFAULT_MAX_WEEKLY_HOURS,
    DEFAULT_SCHEDULER_INTERVAL_HOURS,
    LLM_API_KEY_MASK,
)
from prm.domain.enums import LLMProvider
from prm.domain.exceptions import ValidationError
from prm.infrastructure.db.models import SystemConfigurationModel
from prm.infrastructure.db.repositories import SqlAlchemySystemConfigurationRepository
from prm.infrastructure.security.llm_api_key import FernetLlmApiKeyProtector


def _session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    SystemConfigurationModel.__table__.create(engine, checkfirst=True)
    return Session(engine)


def _service(session: Session) -> SystemConfigService:
    return SystemConfigService(
        config_repository=SqlAlchemySystemConfigurationRepository(session),
        api_key_protector=FernetLlmApiKeyProtector("test-secret-key"),
    )


def test_get_configuration_returns_seeded_defaults() -> None:
    with _session() as session:
        SqlAlchemySystemConfigurationRepository(session).create_with_defaults()
        session.commit()

        summary = _service(session).get_configuration()

        assert summary.llm_provider == LLMProvider.GEMINI
        assert summary.llm_api_key_masked is None
        assert summary.scheduler_interval_hours == DEFAULT_SCHEDULER_INTERVAL_HOURS
        assert summary.max_weekly_hours == DEFAULT_MAX_WEEKLY_HOURS


def test_get_configuration_masks_existing_api_key() -> None:
    with _session() as session:
        repo = SqlAlchemySystemConfigurationRepository(session)
        created = repo.create_with_defaults()
        repo.update(created.id, llm_api_key_encrypted="stored-secret")
        session.commit()

        summary = _service(session).get_configuration()

        assert summary.llm_api_key_masked == LLM_API_KEY_MASK


def test_update_llm_api_key_encrypts_and_masks_value() -> None:
    with _session() as session:
        SqlAlchemySystemConfigurationRepository(session).create_with_defaults()
        session.commit()
        service = _service(session)

        summary = service.update_llm_api_key("  gemini-secret-key  ")
        session.commit()

        assert summary.llm_api_key_masked == LLM_API_KEY_MASK
        stored = SqlAlchemySystemConfigurationRepository(session).find_singleton()
        assert stored is not None
        assert stored.llm_api_key_encrypted != "gemini-secret-key"
        protector = FernetLlmApiKeyProtector("test-secret-key")
        assert protector.decrypt(stored.llm_api_key_encrypted) == "gemini-secret-key"


def test_update_llm_api_key_rejects_blank_value() -> None:
    with _session() as session:
        SqlAlchemySystemConfigurationRepository(session).create_with_defaults()
        session.commit()

        with pytest.raises(ValidationError, match="LLM API key is required"):
            _service(session).update_llm_api_key("   ")


def test_update_llm_provider() -> None:
    with _session() as session:
        SqlAlchemySystemConfigurationRepository(session).create_with_defaults()
        session.commit()

        summary = _service(session).update_llm_provider(LLMProvider.GROQ)
        session.commit()

        assert summary.llm_provider == LLMProvider.GROQ


def test_update_scheduler_interval_hours() -> None:
    with _session() as session:
        SqlAlchemySystemConfigurationRepository(session).create_with_defaults()
        session.commit()

        summary = _service(session).update_scheduler_interval_hours(6)
        session.commit()

        assert summary.scheduler_interval_hours == 6


def test_update_scheduler_interval_hours_rejects_invalid_value() -> None:
    with _session() as session:
        SqlAlchemySystemConfigurationRepository(session).create_with_defaults()
        session.commit()

        with pytest.raises(ValidationError, match="Scheduler interval must be between"):
            _service(session).update_scheduler_interval_hours(0)


def test_update_max_weekly_hours() -> None:
    with _session() as session:
        SqlAlchemySystemConfigurationRepository(session).create_with_defaults()
        session.commit()

        summary = _service(session).update_max_weekly_hours(35)
        session.commit()

        assert summary.max_weekly_hours == 35


def test_update_max_weekly_hours_rejects_invalid_value() -> None:
    with _session() as session:
        SqlAlchemySystemConfigurationRepository(session).create_with_defaults()
        session.commit()

        with pytest.raises(ValidationError, match="Max weekly hours must be between"):
            _service(session).update_max_weekly_hours(200)
