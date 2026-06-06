"""Unit tests for bootstrap admin seed."""

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from prm.domain.enums import Role, UserAccountStatus
from prm.infrastructure.db.models import UserModel
from prm.infrastructure.db.seed import (
    BOOTSTRAP_ADMIN_PASSWORD,
    BOOTSTRAP_ADMIN_USERNAME,
    seed_bootstrap_admin,
)
from prm.infrastructure.security.password import BcryptPasswordHasher


def _session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    UserModel.__table__.create(engine, checkfirst=True)
    return Session(engine)


def test_seed_creates_admin_with_force_password_change() -> None:
    with _session() as session:
        created = seed_bootstrap_admin(session)
        assert created is True

        admin = session.scalar(
            select(UserModel).where(UserModel.username == BOOTSTRAP_ADMIN_USERNAME)
        )
        assert admin is not None
        assert admin.role == Role.ADMIN
        assert admin.account_status == UserAccountStatus.ACTIVE
        assert admin.force_password_change is True

        hasher = BcryptPasswordHasher()
        assert hasher.verify(BOOTSTRAP_ADMIN_PASSWORD, admin.password_hash)


def test_seed_is_idempotent() -> None:
    with _session() as session:
        assert seed_bootstrap_admin(session) is True
        assert seed_bootstrap_admin(session) is False

        admin = session.scalar(
            select(UserModel).where(UserModel.username == BOOTSTRAP_ADMIN_USERNAME)
        )
        assert admin is not None
