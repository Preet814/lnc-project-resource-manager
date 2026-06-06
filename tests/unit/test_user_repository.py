"""Unit tests for SQLAlchemy user repository."""

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from prm.domain.enums import Role, UserAccountStatus
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


def test_find_by_email_returns_domain_user() -> None:
    with _session() as session:
        _seed(session)
        repo = SqlAlchemyUserRepository(session)

        user = repo.find_by_email(TEST_EMAIL)

        assert user is not None
        assert user.username == TEST_USERNAME


def test_find_by_email_returns_none_when_missing() -> None:
    with _session() as session:
        repo = SqlAlchemyUserRepository(session)
        assert repo.find_by_email("missing@example.test") is None


def test_list_all_returns_users_ordered_by_id() -> None:
    with _session() as session:
        _seed(session)
        repo = SqlAlchemyUserRepository(session)
        hasher = BcryptPasswordHasher()
        repo.create(
            full_name="Second User",
            username="second_user",
            email="second@example.test",
            password_hash=hasher.hash("TempPass1"),
            role=Role.EMPLOYEE,
        )
        session.commit()

        users = repo.list_all()

        assert len(users) == 2
        assert users[0].username == TEST_USERNAME
        assert users[1].username == "second_user"


def test_list_all_returns_empty_list_when_no_users() -> None:
    with _session() as session:
        repo = SqlAlchemyUserRepository(session)
        assert repo.list_all() == []


def test_create_persists_user_with_force_password_change() -> None:
    with _session() as session:
        repo = SqlAlchemyUserRepository(session)
        hasher = BcryptPasswordHasher()

        created = repo.create(
            full_name="New Manager",
            username="new_mgr",
            email="new_mgr@example.test",
            password_hash=hasher.hash("TempPass1"),
            role=Role.MANAGER,
        )
        session.commit()

        loaded = repo.find_by_username("new_mgr")
        assert loaded is not None
        assert created.id == loaded.id
        assert loaded.role == Role.MANAGER
        assert loaded.force_password_change is True
        assert loaded.account_status == UserAccountStatus.ACTIVE


def test_update_account_status_changes_status() -> None:
    with _session() as session:
        _seed(session)
        repo = SqlAlchemyUserRepository(session)
        admin = repo.find_by_username(TEST_USERNAME)
        assert admin is not None

        updated = repo.update_account_status(
            admin.id,
            account_status=UserAccountStatus.INACTIVE,
        )
        session.commit()

        assert updated.account_status == UserAccountStatus.INACTIVE
        reloaded = repo.find_by_id(admin.id)
        assert reloaded is not None
        assert reloaded.account_status == UserAccountStatus.INACTIVE


def test_update_account_status_raises_when_user_missing() -> None:
    with _session() as session:
        repo = SqlAlchemyUserRepository(session)
        with pytest.raises(NotFoundError):
            repo.update_account_status(
                999,
                account_status=UserAccountStatus.INACTIVE,
            )
