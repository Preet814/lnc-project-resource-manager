"""Unit tests for bootstrap admin seed."""

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from prm.domain.enums import Role, UserAccountStatus
from prm.infrastructure.db.models import UserModel
from prm.infrastructure.db.seed import seed_bootstrap_admin
from prm.infrastructure.security.password import BcryptPasswordHasher

TEST_ADMIN_USERNAME = "admin"
TEST_ADMIN_PASSWORD = "Admin@1234"
TEST_ADMIN_FULL_NAME = "System Administrator"
TEST_ADMIN_EMAIL = "admin@test.local"


def _session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    UserModel.__table__.create(engine, checkfirst=True)
    return Session(engine)


def _seed(session: Session) -> bool:
    return seed_bootstrap_admin(
        session,
        username=TEST_ADMIN_USERNAME,
        password=TEST_ADMIN_PASSWORD,
        full_name=TEST_ADMIN_FULL_NAME,
        email=TEST_ADMIN_EMAIL,
    )


def test_seed_creates_admin_with_force_password_change() -> None:
    with _session() as session:
        created = _seed(session)
        assert created is True

        admin = session.scalar(
            select(UserModel).where(UserModel.username == TEST_ADMIN_USERNAME)
        )
        assert admin is not None
        assert admin.role == Role.ADMIN
        assert admin.account_status == UserAccountStatus.ACTIVE
        assert admin.force_password_change is True

        hasher = BcryptPasswordHasher()
        assert hasher.verify(TEST_ADMIN_PASSWORD, admin.password_hash)


def test_seed_is_idempotent() -> None:
    with _session() as session:
        assert _seed(session) is True
        assert _seed(session) is False

        admin = session.scalar(
            select(UserModel).where(UserModel.username == TEST_ADMIN_USERNAME)
        )
        assert admin is not None
