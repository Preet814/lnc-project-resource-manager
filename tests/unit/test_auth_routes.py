"""Unit tests for auth HTTP endpoints."""

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from prm.domain.enums import Role, UserAccountStatus
from prm.infrastructure.db.models import EmailVerificationOtpModel
from prm.infrastructure.db.rbac_seed import (
    default_department_id,
    default_designation_id,
    role_id_for_code,
    seed_rbac_lookups,
)
from prm.infrastructure.db.repositories import SqlAlchemyUserRepository
from prm.infrastructure.db.seed import seed_bootstrap_admin
from prm.infrastructure.security.password import BcryptPasswordHasher
from tests.unit.credentials import TEST_EMAIL, TEST_FULL_NAME, TEST_PASSWORD, TEST_USERNAME
from tests.unit.engineer_fixtures import (
    build_test_client,
    create_route_tables,
    create_sqlite_engine,
)


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    engine = create_sqlite_engine()
    create_route_tables(engine)
    EmailVerificationOtpModel.__table__.create(engine, checkfirst=True)
    with Session(engine) as setup:
        seed_bootstrap_admin(
            setup,
            username=TEST_USERNAME,
            password=TEST_PASSWORD,
            full_name=TEST_FULL_NAME,
            email=TEST_EMAIL,
        )
        setup.commit()
    yield from build_test_client(engine)


def test_login_returns_token_and_force_password_change(client: TestClient) -> None:
    response = client.post(
        "/auth/login",
        json={"username": TEST_USERNAME, "password": TEST_PASSWORD},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["access_token"]
    assert body["token_type"] == "bearer"
    assert body["username"] == TEST_USERNAME
    assert body["force_password_change"] is True
    assert body["email_verified"] is True
    assert body["role"] == "ADMIN"


def test_login_returns_401_for_invalid_credentials(client: TestClient) -> None:
    response = client.post(
        "/auth/login",
        json={"username": TEST_USERNAME, "password": "WrongPass1"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid username or password."


def test_change_password_requires_bearer_token(client: TestClient) -> None:
    response = client.post(
        "/auth/change-password",
        json={"new_password": "NewSecure1", "confirm_password": "NewSecure1"},
    )

    assert response.status_code == 401


def test_change_password_clears_force_flag_and_returns_new_token(client: TestClient) -> None:
    login = client.post(
        "/auth/login",
        json={"username": TEST_USERNAME, "password": TEST_PASSWORD},
    )
    token = login.json()["access_token"]

    response = client.post(
        "/auth/change-password",
        headers={"Authorization": f"Bearer {token}"},
        json={"new_password": "NewSecure1", "confirm_password": "NewSecure1"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["force_password_change"] is False
    assert body["access_token"] != token

    relogin = client.post(
        "/auth/login",
        json={"username": TEST_USERNAME, "password": "NewSecure1"},
    )
    assert relogin.status_code == 200
    assert relogin.json()["force_password_change"] is False


def test_change_password_returns_400_when_passwords_mismatch(client: TestClient) -> None:
    login = client.post(
        "/auth/login",
        json={"username": TEST_USERNAME, "password": TEST_PASSWORD},
    )
    token = login.json()["access_token"]

    response = client.post(
        "/auth/change-password",
        headers={"Authorization": f"Bearer {token}"},
        json={"new_password": "NewSecure1", "confirm_password": "Different1"},
    )

    assert response.status_code == 400
    assert "do not match" in response.json()["detail"]


def test_login_returns_email_verified_false_for_unverified_engineer() -> None:
    engine = create_sqlite_engine()
    create_route_tables(engine)
    EmailVerificationOtpModel.__table__.create(engine, checkfirst=True)
    with Session(engine) as session:
        seed_rbac_lookups(session)
        hasher = BcryptPasswordHasher()
        SqlAlchemyUserRepository(session).create(
            full_name="Chinmay Jain",
            username="chinmay",
            email="chinmay@gmail.com",
            password_hash=hasher.hash("TempPass1"),
            role_id=role_id_for_code(session, Role.ENGINEER.value),
            department_id=default_department_id(session, name="Backend"),
            designation_id=default_designation_id(session, name="SE"),
            manager_id=None,
            force_password_change=False,
            account_status=UserAccountStatus.ACTIVE,
        )
        session.commit()

    generator = build_test_client(engine)
    engineer_client = next(generator)
    try:
        response = engineer_client.post(
            "/auth/login",
            json={"username": "chinmay", "password": "TempPass1"},
        )
    finally:
        try:
            next(generator)
        except StopIteration:
            pass

    assert response.status_code == 200
    body = response.json()
    assert body["email_verified"] is False
    assert body["force_password_change"] is False
