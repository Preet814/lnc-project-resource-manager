"""Unit tests for auth HTTP endpoints."""

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from prm.api.app import create_app
from prm.infrastructure.db.models import UserModel
from prm.infrastructure.db.seed import seed_bootstrap_admin
from prm.infrastructure.db.session import get_db_session
from tests.unit.credentials import TEST_EMAIL, TEST_FULL_NAME, TEST_PASSWORD, TEST_USERNAME


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    # StaticPool + check_same_thread=False: TestClient runs handlers in worker threads.
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    UserModel.__table__.create(engine, checkfirst=True)
    with Session(engine) as setup:
        seed_bootstrap_admin(
            setup,
            username=TEST_USERNAME,
            password=TEST_PASSWORD,
            full_name=TEST_FULL_NAME,
            email=TEST_EMAIL,
        )
        setup.commit()

    def override_get_db() -> Generator[Session, None, None]:
        db = Session(engine)
        try:
            yield db
        finally:
            db.close()

    app = create_app()
    app.dependency_overrides[get_db_session] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


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
