"""Unit tests for bootstrap admin seed."""

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, joinedload

from prm.api.settings import Settings
from prm.domain.constants import DEFAULT_MAX_WEEKLY_HOURS, DEFAULT_SCHEDULER_INTERVAL_HOURS
from prm.domain.enums import LLMProvider, UserAccountStatus
from prm.infrastructure.db.models import SystemConfigurationModel, UserModel
from prm.infrastructure.db.seed import (
    ensure_bootstrap_admin_email_verified,
    seed_bootstrap_admin,
    seed_default_system_configuration,
    seed_default_system_configuration_from_settings,
)
from prm.infrastructure.security.llm_api_key import FernetLlmApiKeyProtector
from prm.infrastructure.security.password import BcryptPasswordHasher
from tests.unit.credentials import TEST_EMAIL, TEST_FULL_NAME, TEST_PASSWORD, TEST_USERNAME
from tests.unit.engineer_fixtures import create_rbac_tables


def _session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    create_rbac_tables(engine)
    SystemConfigurationModel.__table__.create(engine, checkfirst=True)
    return Session(engine)


def _seed(session: Session) -> bool:
    return seed_bootstrap_admin(
        session,
        username=TEST_USERNAME,
        password=TEST_PASSWORD,
        full_name=TEST_FULL_NAME,
        email=TEST_EMAIL,
    )


def test_seed_creates_admin_with_force_password_change() -> None:
    with _session() as session:
        created = _seed(session)
        assert created is True

        admin = session.scalar(
            select(UserModel)
            .options(joinedload(UserModel.role))
            .where(UserModel.username == TEST_USERNAME)
        )
        assert admin is not None
        assert admin.role.code == "ADMIN"
        assert admin.account_status == UserAccountStatus.ACTIVE
        assert admin.force_password_change is True
        assert admin.email_verified is True

        hasher = BcryptPasswordHasher()
        assert hasher.verify(TEST_PASSWORD, admin.password_hash)


def test_seed_is_idempotent() -> None:
    with _session() as session:
        assert _seed(session) is True
        assert _seed(session) is False

        admin = session.scalar(
            select(UserModel).where(UserModel.username == TEST_USERNAME)
        )
        assert admin is not None


def test_ensure_bootstrap_admin_email_verified_updates_existing_admin() -> None:
    with _session() as session:
        _seed(session)
        admin = session.scalar(
            select(UserModel).where(UserModel.username == TEST_USERNAME)
        )
        assert admin is not None
        admin.email_verified = False
        session.commit()

        updated = ensure_bootstrap_admin_email_verified(
            session,
            _bootstrap_settings(),
        )
        assert updated is True

        reloaded = session.scalar(
            select(UserModel).where(UserModel.username == TEST_USERNAME)
        )
        assert reloaded is not None
        assert reloaded.email_verified is True
        assert ensure_bootstrap_admin_email_verified(session, _bootstrap_settings()) is False


def test_seed_default_system_configuration_creates_brd_defaults() -> None:
    with _session() as session:
        created = seed_default_system_configuration(session)
        assert created is True

        config = session.scalar(select(SystemConfigurationModel).limit(1))
        assert config is not None
        assert config.llm_provider == LLMProvider.GEMINI
        assert config.llm_api_key_encrypted is None
        assert config.scheduler_interval_hours == DEFAULT_SCHEDULER_INTERVAL_HOURS
        assert config.max_weekly_hours == DEFAULT_MAX_WEEKLY_HOURS


def test_seed_default_system_configuration_is_idempotent() -> None:
    with _session() as session:
        assert seed_default_system_configuration(session) is True
        assert seed_default_system_configuration(session) is False


def _bootstrap_settings(**overrides: object) -> Settings:
    values = {
        "bootstrap_admin_username": TEST_USERNAME,
        "bootstrap_admin_password": TEST_PASSWORD,
        "bootstrap_admin_full_name": TEST_FULL_NAME,
        "bootstrap_admin_email": TEST_EMAIL,
        "jwt_secret_key": "test-jwt-secret-key",
        "bootstrap_llm_provider": "GROQ",
        "bootstrap_llm_api_key": "bootstrap-provider-key",
        "bootstrap_scheduler_interval_hours": 6,
        "bootstrap_max_weekly_hours": 35,
    }
    values.update(overrides)
    return Settings(**values)


def test_seed_default_system_configuration_from_settings_uses_env_values() -> None:
    with _session() as session:
        created = seed_default_system_configuration_from_settings(
            session,
            _bootstrap_settings(),
        )
        assert created is True

        config = session.scalar(select(SystemConfigurationModel).limit(1))
        assert config is not None
        assert config.llm_provider == LLMProvider.GROQ
        assert config.scheduler_interval_hours == 6
        assert config.max_weekly_hours == 35
        assert config.llm_api_key_encrypted is not None

        protector = FernetLlmApiKeyProtector("test-jwt-secret-key")
        assert protector.decrypt(config.llm_api_key_encrypted) == "bootstrap-provider-key"


def test_seed_default_system_configuration_from_settings_is_idempotent() -> None:
    with _session() as session:
        settings = _bootstrap_settings()
        assert seed_default_system_configuration_from_settings(session, settings) is True
        assert seed_default_system_configuration_from_settings(session, settings) is False
