"""Unit tests for UserManagementService."""

import pytest
from sqlalchemy.orm import Session

from prm.application.user_management_service import UserManagementService
from prm.domain.enums import Role, UserAccountStatus
from prm.domain.exceptions import NotFoundError, ValidationError
from prm.infrastructure.db.repositories import SqlAlchemyUserRepository
from prm.infrastructure.db.seed import seed_bootstrap_admin
from prm.infrastructure.security.password import BcryptPasswordHasher
from tests.unit.credentials import TEST_EMAIL, TEST_FULL_NAME, TEST_PASSWORD, TEST_USERNAME
from tests.unit.engineer_fixtures import create_memory_session, seed_rbac


def _session() -> Session:
    return create_memory_session()


def _service(session: Session) -> UserManagementService:
    return UserManagementService(
        user_repository=SqlAlchemyUserRepository(session),
        password_hasher=BcryptPasswordHasher(),
    )


def _seed_admin(session: Session) -> None:
    seed_bootstrap_admin(
        session,
        username=TEST_USERNAME,
        password=TEST_PASSWORD,
        full_name=TEST_FULL_NAME,
        email=TEST_EMAIL,
    )


def _create_engineer(session: Session, *, username: str, email: str) -> int:
    seed_rbac(session)
    created = _service(session).create_user(
        full_name="Test Employee",
        email=email,
        username=username,
        temporary_password="TempPass1",
        role=Role.ENGINEER,
    )
    session.commit()
    return created.id


def test_create_user_persists_with_force_password_change() -> None:
    with _session() as session:
        seed_rbac(session)
        created = _service(session).create_user(
            full_name="New Manager",
            email="mgr@example.test",
            username="new_mgr",
            temporary_password="TempPass1",
            role=Role.MANAGER,
        )
        session.commit()

        assert created.username == "new_mgr"
        assert created.role == Role.MANAGER
        assert created.force_password_change is True
        assert created.account_status == UserAccountStatus.ACTIVE
        assert created.department_id is None
        assert created.designation_id is None


def test_create_user_with_department_and_designation() -> None:
    with _session() as session:
        seed_rbac(session)
        created = _service(session).create_user(
            full_name="Backend Engineer",
            email="backend@example.test",
            username="backend_eng",
            temporary_password="TempPass1",
            role=Role.ENGINEER,
            department="Backend",
            designation="SSE",
        )
        session.commit()

        assert created.department_name == "Backend"
        assert created.designation_name == "SSE"


def test_create_user_fails_when_department_not_found() -> None:
    with _session() as session:
        seed_rbac(session)
        with pytest.raises(ValidationError, match="Department"):
            _service(session).create_user(
                full_name="Bad Dept",
                email="baddept@example.test",
                username="bad_dept",
                temporary_password="TempPass1",
                role=Role.ENGINEER,
                department="Unknown Dept",
            )


def test_create_user_fails_when_username_exists() -> None:
    with _session() as session:
        _seed_admin(session)
        with pytest.raises(ValidationError, match="Username"):
            _service(session).create_user(
                full_name="Duplicate",
                email="other@example.test",
                username=TEST_USERNAME,
                temporary_password="TempPass1",
                role=Role.ENGINEER,
            )


def test_create_user_fails_when_email_exists() -> None:
    with _session() as session:
        _seed_admin(session)
        with pytest.raises(ValidationError, match="Email"):
            _service(session).create_user(
                full_name="Duplicate",
                email=TEST_EMAIL,
                username="other_user",
                temporary_password="TempPass1",
                role=Role.ENGINEER,
            )


def test_create_user_fails_when_password_too_weak() -> None:
    with _session() as session:
        seed_rbac(session)
        with pytest.raises(ValidationError):
            _service(session).create_user(
                full_name="Weak Password User",
                email="weak@example.test",
                username="weak_user",
                temporary_password="weak",
                role=Role.ENGINEER,
            )


def test_list_users_returns_summaries_and_counts() -> None:
    with _session() as session:
        _seed_admin(session)
        user_id = _create_engineer(
            session,
            username="emp_one",
            email="emp_one@example.test",
        )
        _service(session).deactivate_user(user_id, actor_user_id=1)
        session.commit()

        result = _service(session).list_users()

        assert result.total == 2
        assert result.active_count == 1
        assert result.inactive_count == 1
        assert result.users[0].username == TEST_USERNAME
        assert result.users[1].username == "emp_one"
        assert result.users[1].account_status == UserAccountStatus.INACTIVE
        assert result.users[0].department == "IT"
        assert result.users[0].designation == "System Administrator"


def test_reactivate_user_sets_account_active() -> None:
    with _session() as session:
        _seed_admin(session)
        user_id = _create_engineer(
            session,
            username="emp_two",
            email="emp_two@example.test",
        )
        _service(session).deactivate_user(user_id, actor_user_id=1)
        session.commit()

        reactivated = _service(session).reactivate_user(user_id)
        session.commit()

        assert reactivated.account_status == UserAccountStatus.ACTIVE


def test_reactivate_user_fails_when_already_active() -> None:
    with _session() as session:
        _seed_admin(session)
        with pytest.raises(ValidationError, match="already active"):
            _service(session).reactivate_user(1)


def test_reactivate_user_fails_when_user_missing() -> None:
    with _session() as session:
        with pytest.raises(NotFoundError):
            _service(session).reactivate_user(999)


def test_deactivate_user_sets_account_inactive() -> None:
    with _session() as session:
        _seed_admin(session)
        user_id = _create_engineer(
            session,
            username="emp_three",
            email="emp_three@example.test",
        )

        deactivated = _service(session).deactivate_user(user_id, actor_user_id=1)
        session.commit()

        assert deactivated.account_status == UserAccountStatus.INACTIVE


def test_deactivate_user_fails_when_deactivating_self() -> None:
    with _session() as session:
        _seed_admin(session)
        with pytest.raises(ValidationError, match="your own account"):
            _service(session).deactivate_user(1, actor_user_id=1)


def test_deactivate_user_fails_when_already_inactive() -> None:
    with _session() as session:
        _seed_admin(session)
        user_id = _create_engineer(
            session,
            username="emp_four",
            email="emp_four@example.test",
        )
        _service(session).deactivate_user(user_id, actor_user_id=1)
        session.commit()

        with pytest.raises(ValidationError, match="already inactive"):
            _service(session).deactivate_user(user_id, actor_user_id=1)


def test_reset_password_by_username_sets_force_flag() -> None:
    with _session() as session:
        _seed_admin(session)
        user_id = _create_engineer(
            session,
            username="emp_five",
            email="emp_five@example.test",
        )
        _service(session).reset_password("emp_five", temporary_password="ResetPass1")
        session.commit()

        updated = SqlAlchemyUserRepository(session).find_by_id(user_id)
        assert updated is not None
        assert updated.force_password_change is True
        assert BcryptPasswordHasher().verify("ResetPass1", updated.password_hash)


def test_reset_password_by_id_sets_force_flag() -> None:
    with _session() as session:
        _seed_admin(session)
        user_id = _create_engineer(
            session,
            username="emp_six",
            email="emp_six@example.test",
        )
        _service(session).reset_password(str(user_id), temporary_password="ResetPass2")
        session.commit()

        updated = SqlAlchemyUserRepository(session).find_by_id(user_id)
        assert updated is not None
        assert updated.force_password_change is True
        assert BcryptPasswordHasher().verify("ResetPass2", updated.password_hash)


def test_reset_password_fails_when_user_missing() -> None:
    with _session() as session:
        with pytest.raises(NotFoundError):
            _service(session).reset_password("missing_user", temporary_password="ResetPass1")


def test_reset_password_fails_when_password_too_weak() -> None:
    with _session() as session:
        _seed_admin(session)
        with pytest.raises(ValidationError):
            _service(session).reset_password(TEST_USERNAME, temporary_password="weak")


def test_reset_password_fails_when_identifier_empty() -> None:
    with _session() as session:
        with pytest.raises(ValidationError, match="identifier is required"):
            _service(session).reset_password("   ", temporary_password="ResetPass1")
