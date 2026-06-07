"""Unit tests for admin allocation-view and system-config HTTP endpoints."""

from collections.abc import Generator
from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from prm.api.app import create_app
from prm.domain.enums import AllocationStatus, Role
from prm.infrastructure.db.models import (
    AllocationModel,
    EmployeeModel,
    ProjectModel,
    SystemConfigurationModel,
    UserModel,
)
from prm.infrastructure.db.repositories import (
    SqlAlchemyEmployeeRepository,
    SqlAlchemyUserRepository,
)
from prm.infrastructure.db.seed import seed_bootstrap_admin, seed_default_system_configuration
from prm.infrastructure.db.session import get_db_session
from prm.infrastructure.security.password import BcryptPasswordHasher
from tests.unit.credentials import TEST_EMAIL, TEST_FULL_NAME, TEST_PASSWORD, TEST_USERNAME

MANAGER_USERNAME = "test_manager"
MANAGER_PASSWORD = "TestPass9"
MANAGER_EMAIL = "test_manager@example.test"
EMPLOYEE_USERNAME = "test_employee"
EMPLOYEE_PASSWORD = "TestPass9"
EMPLOYEE_EMAIL = "test_employee@example.test"


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
    SystemConfigurationModel.__table__.create(engine, checkfirst=True)

    with Session(engine) as setup:
        seed_bootstrap_admin(
            setup,
            username=TEST_USERNAME,
            password=TEST_PASSWORD,
            full_name=TEST_FULL_NAME,
            email=TEST_EMAIL,
        )
        seed_default_system_configuration(setup)
        repo = SqlAlchemyUserRepository(setup)
        hasher = BcryptPasswordHasher()
        manager = repo.create(
            full_name="Test Manager",
            username=MANAGER_USERNAME,
            email=MANAGER_EMAIL,
            password_hash=hasher.hash(MANAGER_PASSWORD),
            role=Role.MANAGER,
            force_password_change=False,
        )
        employee_user = repo.create(
            full_name="Ravi Kumar",
            username=EMPLOYEE_USERNAME,
            email=EMPLOYEE_EMAIL,
            password_hash=hasher.hash(EMPLOYEE_PASSWORD),
            role=Role.EMPLOYEE,
            force_password_change=False,
        )
        employee_repo = SqlAlchemyEmployeeRepository(setup)
        employee = employee_repo.create(
            user_id=employee_user.id,
            full_name="Ravi Kumar",
            email=EMPLOYEE_EMAIL,
            department="Backend",
            designation="Developer",
        )
        project = ProjectModel(
            name="Alpha Portal",
            description="Test project",
            start_date=date(2026, 3, 1),
            end_date=date(2026, 6, 30),
            manager_user_id=manager.id,
        )
        setup.add(project)
        setup.flush()
        setup.add(
            AllocationModel(
                employee_id=employee.id,
                project_id=project.id,
                utilisation_percent=50,
                from_date=date(2026, 3, 1),
                to_date=date(2026, 6, 30),
                status=AllocationStatus.ACTIVE,
                created_by_user_id=manager.id,
            )
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


def test_list_allocations_requires_bearer_token(client: TestClient) -> None:
    response = client.get("/admin/allocations")
    assert response.status_code == 401


def test_list_allocations_returns_403_for_non_admin(client: TestClient) -> None:
    token = _login_token(client, username=MANAGER_USERNAME, password=MANAGER_PASSWORD)
    response = client.get(
        "/admin/allocations",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


def test_list_allocations_returns_enriched_rows(client: TestClient) -> None:
    response = client.get("/admin/allocations", headers=_admin_headers(client))

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    row = body["allocations"][0]
    assert row["employee_full_name"] == "Ravi Kumar"
    assert row["project_name"] == "Alpha Portal"
    assert row["utilisation_percent"] == 50


def test_list_allocations_filters_by_employee_id(client: TestClient) -> None:
    listing = client.get("/admin/allocations", headers=_admin_headers(client)).json()
    employee_id = listing["allocations"][0]["employee_id"]

    response = client.get(
        f"/admin/allocations?employee_id={employee_id}",
        headers=_admin_headers(client),
    )

    assert response.status_code == 200
    assert response.json()["total"] == 1


def test_get_configuration_requires_bearer_token(client: TestClient) -> None:
    response = client.get("/admin/config")
    assert response.status_code == 401


def test_get_configuration_returns_defaults(client: TestClient) -> None:
    response = client.get("/admin/config", headers=_admin_headers(client))

    assert response.status_code == 200
    body = response.json()
    assert body["llm_provider"] == "GEMINI"
    assert body["llm_api_key_masked"] is None
    assert body["scheduler_interval_hours"] == 4
    assert body["max_weekly_hours"] == 40


def test_update_llm_api_key_masks_value(client: TestClient) -> None:
    response = client.patch(
        "/admin/config/llm-api-key",
        headers=_admin_headers(client),
        json={"api_key": "gemini-secret-key"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["llm_api_key_masked"] == "*" * 28


def test_update_llm_api_key_returns_400_for_blank_value(client: TestClient) -> None:
    response = client.patch(
        "/admin/config/llm-api-key",
        headers=_admin_headers(client),
        json={"api_key": "   "},
    )

    assert response.status_code == 400
    assert "LLM API key is required" in response.json()["detail"]


def test_update_llm_provider(client: TestClient) -> None:
    response = client.patch(
        "/admin/config/llm-provider",
        headers=_admin_headers(client),
        json={"provider": "GROQ"},
    )

    assert response.status_code == 200
    assert response.json()["llm_provider"] == "GROQ"


def test_update_scheduler_interval(client: TestClient) -> None:
    response = client.patch(
        "/admin/config/scheduler-interval",
        headers=_admin_headers(client),
        json={"scheduler_interval_hours": 6},
    )

    assert response.status_code == 200
    assert response.json()["scheduler_interval_hours"] == 6


def test_update_max_weekly_hours(client: TestClient) -> None:
    response = client.patch(
        "/admin/config/max-weekly-hours",
        headers=_admin_headers(client),
        json={"max_weekly_hours": 35},
    )

    assert response.status_code == 200
    assert response.json()["max_weekly_hours"] == 35
