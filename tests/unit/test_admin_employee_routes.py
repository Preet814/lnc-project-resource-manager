"""Unit tests for admin engineer-profile HTTP endpoints."""

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from prm.domain.enums import Role
from prm.infrastructure.db.seed import seed_bootstrap_admin
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
    create_route_tables(
        engine,
        include_project=True,
        include_allocation=True,
        include_skill=True,
    )
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


def _create_user(client: TestClient, *, username: str, email: str) -> dict:
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


def _create_engineer_profile(client: TestClient, *, username: str, email: str) -> dict:
    user = _create_user(client, username=username, email=email)
    response = client.post(
        "/admin/employees",
        headers=_admin_headers(client),
        json={
            "user_id": user["id"],
            "full_name": "Route Test Engineer",
            "email": email,
            "department": "Backend",
            "designation": "SE",
        },
    )
    assert response.status_code == 201
    return response.json()


def test_create_employee_returns_201(client: TestClient) -> None:
    created = _create_engineer_profile(
        client,
        username="route.engineer",
        email="route.engineer@example.test",
    )
    assert created["id"]
    assert created["work_status"] == "BENCH"


def test_list_employees_returns_engineers(client: TestClient) -> None:
    created = _create_engineer_profile(
        client,
        username="list.engineer",
        email="list.engineer@example.test",
    )
    response = client.get("/admin/employees", headers=_admin_headers(client))
    assert response.status_code == 200
    body = response.json()
    assert created["id"] in {row["id"] for row in body["engineers"]}


def test_assign_manager_returns_200(client: TestClient) -> None:
    engineer_user = _create_user(
        client,
        username="assign.engineer",
        email="assign.engineer@example.test",
    )
    manager_response = client.post(
        "/admin/users",
        headers=_admin_headers(client),
        json={
            "full_name": "Assign Manager",
            "email": "assign.manager@example.test",
            "username": "assign.manager",
            "temporary_password": "TempPass1",
            "role": "MANAGER",
        },
    )
    assert manager_response.status_code == 201
    manager_user = manager_response.json()
    client.post(
        "/admin/employees",
        headers=_admin_headers(client),
        json={
            "user_id": engineer_user["id"],
            "full_name": "Assign Engineer",
            "email": engineer_user["email"],
            "department": "Backend",
            "designation": "SE",
        },
    )
    response = client.post(
        "/admin/employees/assign-manager",
        headers=_admin_headers(client),
        json={
            "engineer_user_id": engineer_user["id"],
            "manager_user_id": manager_user["id"],
        },
    )
    assert response.status_code == 200
    assert response.json()["manager_id"] == manager_user["id"]


def test_add_user_skill_returns_201(client: TestClient) -> None:
    employee = _create_engineer_profile(
        client,
        username="skill.engineer",
        email="skill.engineer@example.test",
    )
    response = client.post(
        f"/admin/employees/{employee['id']}/skills",
        headers=_admin_headers(client),
        json={
            "skill_name": "Docker",
            "category": "DEVOPS",
            "proficiency": "BEGINNER",
        },
    )
    assert response.status_code == 201
    assert response.json()["user_skill_id"]


def test_update_user_skill_returns_new_proficiency(client: TestClient) -> None:
    employee = _create_engineer_profile(
        client,
        username="skill.update",
        email="skill.update@example.test",
    )
    added = client.post(
        f"/admin/employees/{employee['id']}/skills",
        headers=_admin_headers(client),
        json={
            "skill_name": "Python",
            "category": "BACKEND",
            "proficiency": "BEGINNER",
        },
    ).json()
    response = client.patch(
        f"/admin/employees/{employee['id']}/skills/{added['user_skill_id']}",
        headers=_admin_headers(client),
        json={"proficiency": "ADVANCED"},
    )
    assert response.status_code == 200
    assert response.json()["proficiency"] == "ADVANCED"


def test_get_employee_returns_200(client: TestClient) -> None:
    created = _create_engineer_profile(
        client,
        username="get.engineer",
        email="get.engineer@example.test",
    )
    response = client.get(
        f"/admin/employees/{created['id']}",
        headers=_admin_headers(client),
    )
    assert response.status_code == 200
    assert response.json()["id"] == created["id"]


def test_update_employee_returns_200(client: TestClient) -> None:
    created = _create_engineer_profile(
        client,
        username="patch.engineer",
        email="patch.engineer@example.test",
    )
    response = client.patch(
        f"/admin/employees/{created['id']}",
        headers=_admin_headers(client),
        json={
            "full_name": "Updated Engineer",
            "email": "updated.engineer@example.test",
            "department": "Frontend",
            "designation": "SSE",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["full_name"] == "Updated Engineer"
    assert body["department"] == "Frontend"


def test_deactivate_employee_returns_200(client: TestClient) -> None:
    created = _create_engineer_profile(
        client,
        username="deactivate.engineer",
        email="deactivate.engineer@example.test",
    )
    response = client.post(
        f"/admin/employees/{created['id']}/deactivate",
        headers=_admin_headers(client),
    )
    assert response.status_code == 200
    assert response.json()["is_active"] is False


def test_remove_user_skill_returns_204(client: TestClient) -> None:
    employee = _create_engineer_profile(
        client,
        username="skill.remove",
        email="skill.remove@example.test",
    )
    added = client.post(
        f"/admin/employees/{employee['id']}/skills",
        headers=_admin_headers(client),
        json={
            "skill_name": "Kubernetes",
            "category": "DEVOPS",
            "proficiency": "INTERMEDIATE",
        },
    ).json()
    response = client.delete(
        f"/admin/employees/{employee['id']}/skills/{added['user_skill_id']}",
        headers=_admin_headers(client),
    )
    assert response.status_code == 204
