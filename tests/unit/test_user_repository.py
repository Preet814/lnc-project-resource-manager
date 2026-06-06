"""Unit tests for SQLAlchemy user repository."""

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from prm.domain.enums import Role
from prm.domain.exceptions import NotFoundError
from prm.infrastructure.db.models import UserModel
from prm.infrastructure.db.repositories import SqlAlchemyUserRepository
from prm.infrastructure.db.seed import seed_bootstrap_admin
from prm.infrastructure.security.password import BcryptPasswordHasher
from tests.unit.credentials import TEST_EMAIL, TEST_FULL_NAME, TEST_PASSWORD, TEST_USERNAME


def _session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    UserModel.__table__.create(engine, checkfirst=True)
    return Session(engine)


def _seed(session: Session) -> None:
    seed_bootstrap_admin(
        session,
        username=TEST_USERNAME,
        password=TEST_PASSWORD,
        full_name=TEST_FULL_NAME,
        email=TEST_EMAIL,
    )


def test_find_by_username_returns_domain_user() -> None:
    with _session() as session:
        _seed(session)
        repo = SqlAlchemyUserRepository(session)

        user = repo.find_by_username(TEST_USERNAME)

        assert user is not None
        assert user.username == TEST_USERNAME
        assert user.role == Role.ADMIN
        assert user.force_password_change is True


def test_find_by_id_returns_domain_user() -> None:
    with _session() as session:
        _seed(session)
        repo = SqlAlchemyUserRepository(session)
        model = session.scalar(
            select(UserModel).where(UserModel.username == TEST_USERNAME)
        )
        assert model is not None

        user = repo.find_by_id(model.id)

        assert user is not None
        assert user.id == model.id
        assert user.email == TEST_EMAIL


def test_find_by_username_returns_none_when_missing() -> None:
    with _session() as session:
        repo = SqlAlchemyUserRepository(session)
        assert repo.find_by_username("missing") is None


def test_update_password_changes_hash_and_flag() -> None:
    with _session() as session:
        _seed(session)
        repo = SqlAlchemyUserRepository(session)
        admin = repo.find_by_username(TEST_USERNAME)
        assert admin is not None

        hasher = BcryptPasswordHasher()
        new_hash = hasher.hash("NewPass1")
        updated = repo.update_password(
            admin.id,
            password_hash=new_hash,
            force_password_change=False,
        )
        session.commit()

        assert updated.force_password_change is False
        assert hasher.verify("NewPass1", updated.password_hash)
        assert not hasher.verify(TEST_PASSWORD, updated.password_hash)


def test_update_password_raises_when_user_missing() -> None:
    with _session() as session:
        repo = SqlAlchemyUserRepository(session)
        with pytest.raises(NotFoundError):
            repo.update_password(
                999,
                password_hash="hash",
                force_password_change=False,
            )
