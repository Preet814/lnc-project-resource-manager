"""Unit tests for admin user-management HTTP endpoints."""

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from prm.api.app import create_app
from prm.domain.enums import Role
from prm.infrastructure.db.models import UserModel
from prm.infrastructure.db.repositories import SqlAlchemyUserRepository
from prm.infrastructure.db.seed import seed_bootstrap_admin
from prm.infrastructure.db.session import get_db_session
from prm.infrastructure.security.password import BcryptPasswordHasher
from tests.unit.credentials import TEST_EMAIL, TEST_FULL_NAME, TEST_PASSWORD, TEST_USERNAME

MANAGER_USERNAME = "test_manager"
MANAGER_PASSWORD = "TestPass9"
MANAGER_EMAIL = "test_manager@example.test"


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
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
        repo = SqlAlchemyUserRepository(setup)
        hasher = BcryptPasswordHasher()
        repo.create(
            full_name="Test Manager",
            username=MANAGER_USERNAME,
            email=MANAGER_EMAIL,
            password_hash=hasher.hash(MANAGER_PASSWORD),
            role=Role.MANAGER,
            force_password_change=False,
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


def _create_employee(client: TestClient, *, username: str, email: str) -> dict:
    response = client.post(
        "/admin/users",
        headers=_admin_headers(client),
        json={
            "full_name": "Route Test Employee",
            "email": email,
            "username": username,
            "temporary_password": "TempPass1",
            "role": "EMPLOYEE",
        },
    )
    assert response.status_code == 201
    return response.json()


def test_list_users_requires_bearer_token(client: TestClient) -> None:
    response = client.get("/admin/users")
    assert response.status_code == 401


def test_list_users_returns_403_for_non_admin(client: TestClient) -> None:
    token = _login_token(client, username=MANAGER_USERNAME, password=MANAGER_PASSWORD)
    response = client.get(
        "/admin/users",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


def test_list_users_returns_summaries_and_counts(client: TestClient) -> None:
    _create_employee(client, username="emp_list", email="emp_list@example.test")

    response = client.get("/admin/users", headers=_admin_headers(client))

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 3
    assert body["active_count"] == 3
    assert body["inactive_count"] == 0
    usernames = {user["username"] for user in body["users"]}
    assert usernames == {TEST_USERNAME, MANAGER_USERNAME, "emp_list"}


def test_create_user_returns_201_with_force_password_change(client: TestClient) -> None:
    response = client.post(
        "/admin/users",
        headers=_admin_headers(client),
        json={
            "full_name": "New Employee",
            "email": "new_emp@example.test",
            "username": "new_emp",
            "temporary_password": "TempPass1",
            "role": "EMPLOYEE",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["username"] == "new_emp"
    assert body["role"] == "EMPLOYEE"
    assert body["account_status"] == "ACTIVE"
    assert body["force_password_change"] is True


def test_create_user_returns_400_for_duplicate_username(client: TestClient) -> None:
    response = client.post(
        "/admin/users",
        headers=_admin_headers(client),
        json={
            "full_name": "Duplicate",
            "email": "dup@example.test",
            "username": TEST_USERNAME,
            "temporary_password": "TempPass1",
            "role": "EMPLOYEE",
        },
    )

    assert response.status_code == 400
    assert "Username" in response.json()["detail"]


def test_create_user_returns_400_for_weak_password(client: TestClient) -> None:
    response = client.post(
        "/admin/users",
        headers=_admin_headers(client),
        json={
            "full_name": "Weak Password",
            "email": "weak@example.test",
            "username": "weak_user",
            "temporary_password": "weak",
            "role": "EMPLOYEE",
        },
    )

    assert response.status_code == 400


def test_deactivate_user_returns_inactive_status(client: TestClient) -> None:
    created = _create_employee(client, username="emp_deact", email="emp_deact@example.test")

    response = client.post(
        f"/admin/users/{created['id']}/deactivate",
        headers=_admin_headers(client),
    )

    assert response.status_code == 200
    assert response.json()["account_status"] == "INACTIVE"


def test_deactivate_user_returns_400_when_deactivating_self(client: TestClient) -> None:
    login = client.post(
        "/auth/login",
        json={"username": TEST_USERNAME, "password": TEST_PASSWORD},
    )
    admin_id = login.json()["user_id"]

    response = client.post(
        f"/admin/users/{admin_id}/deactivate",
        headers=_admin_headers(client),
    )

    assert response.status_code == 400
    assert "your own account" in response.json()["detail"]


def test_reactivate_user_returns_active_status(client: TestClient) -> None:
    created = _create_employee(client, username="emp_react", email="emp_react@example.test")
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


def test_reset_password_by_username_sets_force_flag(client: TestClient) -> None:
    _create_employee(client, username="emp_reset", email="emp_reset@example.test")

    response = client.post(
        "/admin/users/reset-password",
        headers=_admin_headers(client),
        json={"identifier": "emp_reset", "temporary_password": "ResetPass1"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["username"] == "emp_reset"
    assert body["force_password_change"] is True


def test_reset_password_returns_404_for_missing_user(client: TestClient) -> None:
    response = client.post(
        "/admin/users/reset-password",
        headers=_admin_headers(client),
        json={"identifier": "missing_user", "temporary_password": "ResetPass1"},
    )

    assert response.status_code == 404
