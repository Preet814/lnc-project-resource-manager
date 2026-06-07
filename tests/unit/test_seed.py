"""Unit tests for bootstrap admin seed."""

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from prm.domain.constants import DEFAULT_MAX_WEEKLY_HOURS, DEFAULT_SCHEDULER_INTERVAL_HOURS
from prm.domain.enums import LLMProvider, Role, UserAccountStatus
from prm.infrastructure.db.models import SystemConfigurationModel, UserModel
from prm.infrastructure.db.seed import seed_bootstrap_admin, seed_default_system_configuration
from prm.infrastructure.security.password import BcryptPasswordHasher
from tests.unit.credentials import TEST_EMAIL, TEST_FULL_NAME, TEST_PASSWORD, TEST_USERNAME


def _session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    UserModel.__table__.create(engine, checkfirst=True)
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
            select(UserModel).where(UserModel.username == TEST_USERNAME)
        )
        assert admin is not None
        assert admin.role == Role.ADMIN
        assert admin.account_status == UserAccountStatus.ACTIVE
        assert admin.force_password_change is True

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
