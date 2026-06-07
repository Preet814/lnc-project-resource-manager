"""Unit tests for admin employee-management HTTP endpoints."""

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from prm.api.app import create_app
from prm.domain.enums import Role
from prm.infrastructure.db.models import (
    AllocationModel,
    EmployeeModel,
    EmployeeSkillModel,
    ProjectModel,
    SkillModel,
    UserModel,
)
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
    EmployeeModel.__table__.create(engine, checkfirst=True)
    ProjectModel.__table__.create(engine, checkfirst=True)
    AllocationModel.__table__.create(engine, checkfirst=True)
    SkillModel.__table__.create(engine, checkfirst=True)
    EmployeeSkillModel.__table__.create(engine, checkfirst=True)

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


def _create_user(client: TestClient, *, username: str, email: str) -> dict:
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


def _create_employee(client: TestClient, *, username: str, email: str) -> dict:
    user = _create_user(client, username=username, email=email)
    response = client.post(
        "/admin/employees",
        headers=_admin_headers(client),
        json={
            "user_id": user["id"],
            "full_name": "Route Test Employee",
            "email": email,
            "department": "Backend",
            "designation": "Developer",
        },
    )
    assert response.status_code == 201
    return response.json()


def test_list_employees_requires_bearer_token(client: TestClient) -> None:
    response = client.get("/admin/employees")
    assert response.status_code == 401


def test_list_employees_returns_403_for_non_admin(client: TestClient) -> None:
    token = _login_token(client, username=MANAGER_USERNAME, password=MANAGER_PASSWORD)
    response = client.get(
        "/admin/employees",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


def test_create_employee_returns_201_with_bench_status(client: TestClient) -> None:
    user = _create_user(client, username="emp_create", email="emp_create@example.test")

    response = client.post(
        "/admin/employees",
        headers=_admin_headers(client),
        json={
            "user_id": user["id"],
            "full_name": "New Employee",
            "email": "emp_create@example.test",
            "department": "DevOps",
            "designation": "Engineer",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["user_id"] == user["id"]
    assert body["work_status"] == "BENCH"
    assert body["is_active"] is True
    assert body["department"] == "DevOps"


def test_create_employee_returns_400_for_admin_user(client: TestClient) -> None:
    login = client.post(
        "/auth/login",
        json={"username": TEST_USERNAME, "password": TEST_PASSWORD},
    )
    admin_id = login.json()["user_id"]

    response = client.post(
        "/admin/employees",
        headers=_admin_headers(client),
        json={
            "user_id": admin_id,
            "full_name": "Admin Profile",
            "email": "admin_profile@example.test",
            "department": "IT",
            "designation": "Administrator",
        },
    )

    assert response.status_code == 400
    assert "Employee or Manager" in response.json()["detail"]


def test_list_employees_returns_summaries_and_counts(client: TestClient) -> None:
    _create_employee(client, username="emp_list", email="emp_list@example.test")

    response = client.get("/admin/employees", headers=_admin_headers(client))

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["bench_count"] == 1
    assert body["allocated_count"] == 0
    assert body["employees"][0]["full_name"] == "Route Test Employee"


def test_get_employee_returns_profile(client: TestClient) -> None:
    created = _create_employee(client, username="emp_get", email="emp_get@example.test")

    response = client.get(
        f"/admin/employees/{created['id']}",
        headers=_admin_headers(client),
    )

    assert response.status_code == 200
    assert response.json()["id"] == created["id"]
    assert response.json()["email"] == "emp_get@example.test"


def test_get_employee_returns_404_for_missing(client: TestClient) -> None:
    response = client.get("/admin/employees/999", headers=_admin_headers(client))
    assert response.status_code == 404


def test_update_employee_returns_updated_fields(client: TestClient) -> None:
    created = _create_employee(client, username="emp_update", email="emp_update@example.test")

    response = client.patch(
        f"/admin/employees/{created['id']}",
        headers=_admin_headers(client),
        json={"department": "Frontend", "designation": "Senior Developer"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["department"] == "Frontend"
    assert body["designation"] == "Senior Developer"


def test_deactivate_employee_returns_inactive_profile(client: TestClient) -> None:
    created = _create_employee(
        client, username="emp_deact", email="emp_deact@example.test"
    )

    response = client.post(
        f"/admin/employees/{created['id']}/deactivate",
        headers=_admin_headers(client),
    )

    assert response.status_code == 200
    assert response.json()["is_active"] is False


def test_add_employee_skill_returns_201(client: TestClient) -> None:
    employee = _create_employee(client, username="emp_skill", email="emp_skill@example.test")

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
    body = response.json()
    assert body["skill_name"] == "Docker"
    assert body["category"] == "DEVOPS"
    assert body["proficiency"] == "BEGINNER"


def test_list_employee_skills_returns_added_skills(client: TestClient) -> None:
    employee = _create_employee(
        client, username="emp_skills_list", email="emp_skills_list@example.test"
    )
    client.post(
        f"/admin/employees/{employee['id']}/skills",
        headers=_admin_headers(client),
        json={
            "skill_name": "Java",
            "category": "BACKEND",
            "proficiency": "INTERMEDIATE",
        },
    )

    response = client.get(
        f"/admin/employees/{employee['id']}/skills",
        headers=_admin_headers(client),
    )

    assert response.status_code == 200
    skills = response.json()["skills"]
    assert len(skills) == 1
    assert skills[0]["skill_name"] == "Java"


def test_update_employee_skill_returns_new_proficiency(client: TestClient) -> None:
    employee = _create_employee(
        client, username="emp_skill_upd", email="emp_skill_upd@example.test"
    )
    added = client.post(
        f"/admin/employees/{employee['id']}/skills",
        headers=_admin_headers(client),
        json={
            "skill_name": "Kubernetes",
            "category": "DEVOPS",
            "proficiency": "BEGINNER",
        },
    ).json()

    response = client.patch(
        f"/admin/employees/{employee['id']}/skills/{added['employee_skill_id']}",
        headers=_admin_headers(client),
        json={"proficiency": "ADVANCED"},
    )

    assert response.status_code == 200
    assert response.json()["proficiency"] == "ADVANCED"


def test_remove_employee_skill_returns_204(client: TestClient) -> None:
    employee = _create_employee(
        client, username="emp_skill_rm", email="emp_skill_rm@example.test"
    )
    added = client.post(
        f"/admin/employees/{employee['id']}/skills",
        headers=_admin_headers(client),
        json={
            "skill_name": "React",
            "category": "FRONTEND",
            "proficiency": "INTERMEDIATE",
        },
    ).json()

    response = client.delete(
        f"/admin/employees/{employee['id']}/skills/{added['employee_skill_id']}",
        headers=_admin_headers(client),
    )

    assert response.status_code == 204
    listed = client.get(
        f"/admin/employees/{employee['id']}/skills",
        headers=_admin_headers(client),
    )
    assert listed.json()["skills"] == []


def test_add_employee_skill_returns_400_for_duplicate(client: TestClient) -> None:
    employee = _create_employee(
        client, username="emp_skill_dup", email="emp_skill_dup@example.test"
    )
    client.post(
        f"/admin/employees/{employee['id']}/skills",
        headers=_admin_headers(client),
        json={
            "skill_name": "Python",
            "category": "BACKEND",
            "proficiency": "INTERMEDIATE",
        },
    )

    response = client.post(
        f"/admin/employees/{employee['id']}/skills",
        headers=_admin_headers(client),
        json={
            "skill_name": "Python",
            "category": "BACKEND",
            "proficiency": "ADVANCED",
        },
    )

    assert response.status_code == 400
    assert "already has skill" in response.json()["detail"]
