"""Unit tests for admin user-management HTTP endpoints."""

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from prm.domain.enums import Role
from prm.infrastructure.db.models import UserModel
from prm.infrastructure.db.seed import seed_bootstrap_admin
from prm.infrastructure.security.password import BcryptPasswordHasher
from tests.unit.credentials import TEST_EMAIL, TEST_FULL_NAME, TEST_PASSWORD, TEST_USERNAME
from tests.unit.engineer_fixtures import (
    build_test_client,
    create_route_tables,
    create_sqlite_engine,
    create_user,
    mark_user_onboarded,
)

MANAGER_USERNAME = "test_manager"
MANAGER_PASSWORD = "TestPass9"
MANAGER_EMAIL = "test_manager@example.test"


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    engine = create_sqlite_engine()
    create_route_tables(engine)
    with Session(engine) as setup:
        seed_bootstrap_admin(
            setup,
            username=TEST_USERNAME,
            password=TEST_PASSWORD,
            full_name=TEST_FULL_NAME,
            email=TEST_EMAIL,
        )
        mark_user_onboarded(setup, username=TEST_USERNAME, password=TEST_PASSWORD)
        create_user(
            setup,
            full_name="Test Manager",
            username=MANAGER_USERNAME,
            email=MANAGER_EMAIL,
            role=Role.MANAGER,
            department_name="Delivery",
            designation_name="Project Manager",
        )
        manager = setup.scalar(select(UserModel).where(UserModel.username == MANAGER_USERNAME))
        assert manager is not None
        manager.password_hash = BcryptPasswordHasher().hash(MANAGER_PASSWORD)
        manager.force_password_change = False
        setup.commit()
    yield from build_test_client(engine)


def _login_token(client: TestClient, *, username: str, password: str) -> str:
    response = client.post(
        "/auth/login",
        json={"username": username, "password": password},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def _admin_headers(client: TestClient) -> dict[str, str]:
    token = _login_token(client, username=TEST_USERNAME, password=TEST_PASSWORD)
    return {"Authorization": f"Bearer {token}"}


def _create_engineer(client: TestClient, *, username: str, email: str) -> dict:
    response = client.post(
        "/admin/users",
        headers=_admin_headers(client),
        json={
            "full_name": "Route Test Engineer",
            "email": email,
            "username": username,
            "temporary_password": "TempPass1",
            "role": "ENGINEER",
        },
    )
    assert response.status_code == 201
    return response.json()


def test_list_users_requires_bearer_token(client: TestClient) -> None:
    response = client.get("/admin/users")
    assert response.status_code == 401


def test_list_users_returns_users_for_admin(client: TestClient) -> None:
    response = client.get("/admin/users", headers=_admin_headers(client))
    assert response.status_code == 200
    body = response.json()
    assert body["total"] >= 1
    assert any(user["username"] == TEST_USERNAME for user in body["users"])


def test_create_user_returns_201(client: TestClient) -> None:
    created = _create_engineer(
        client,
        username="new.engineer",
        email="new.engineer@example.test",
    )
    assert created["role"] == "ENGINEER"
    assert created["force_password_change"] is True


def test_create_user_returns_400_for_duplicate_username(client: TestClient) -> None:
    _create_engineer(client, username="dup.user", email="dup1@example.test")
    response = client.post(
        "/admin/users",
        headers=_admin_headers(client),
        json={
            "full_name": "Duplicate",
            "email": "dup2@example.test",
            "username": "dup.user",
            "temporary_password": "TempPass1",
            "role": "ENGINEER",
        },
    )
    assert response.status_code == 400


def test_deactivate_user_returns_200(client: TestClient) -> None:
    created = _create_engineer(
        client,
        username="deactivate.me",
        email="deactivate.me@example.test",
    )
    response = client.post(
        f"/admin/users/{created['id']}/deactivate",
        headers=_admin_headers(client),
    )
    assert response.status_code == 200
    assert response.json()["account_status"] == "INACTIVE"


def test_reactivate_user_returns_200(client: TestClient) -> None:
    created = _create_engineer(
        client,
        username="reactivate.me",
        email="reactivate.me@example.test",
    )
    client.post(
        f"/admin/users/{created['id']}/deactivate",
        headers=_admin_headers(client),
    )
    response = client.post(
        f"/admin/users/{created['id']}/reactivate",
        headers=_admin_headers(client),
    )
    assert response.status_code == 200
    assert response.json()["account_status"] == "ACTIVE"


def test_list_users_returns_403_for_manager(client: TestClient) -> None:
    token = _login_token(client, username=MANAGER_USERNAME, password=MANAGER_PASSWORD)
    response = client.get(
        "/admin/users",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


def test_reset_password_returns_200(client: TestClient) -> None:
    created = _create_engineer(
        client,
        username="reset.me",
        email="reset.me@example.test",
    )
    response = client.post(
        "/admin/users/reset-password",
        headers=_admin_headers(client),
        json={"identifier": created["username"], "temporary_password": "ResetPass1"},
    )
    assert response.status_code == 200
    assert response.json()["force_password_change"] is True
