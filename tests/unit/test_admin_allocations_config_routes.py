"""Unit tests for admin allocation-view and system-config HTTP endpoints."""

from collections.abc import Generator
from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from prm.domain.enums import AllocationStatus, Role
from prm.infrastructure.db.models import AllocationModel, ProjectModel, UserModel
from prm.infrastructure.db.seed import seed_bootstrap_admin, seed_default_system_configuration
from prm.infrastructure.security.password import BcryptPasswordHasher
from tests.unit.credentials import TEST_EMAIL, TEST_FULL_NAME, TEST_PASSWORD, TEST_USERNAME
from tests.unit.engineer_fixtures import (
    build_test_client,
    create_sqlite_engine,
    create_user,
    mark_user_onboarded,
)

MANAGER_USERNAME = "test_manager"
MANAGER_PASSWORD = "TestPass9"
MANAGER_EMAIL = "test_manager@example.test"
EMPLOYEE_USERNAME = "test_employee"
EMPLOYEE_PASSWORD = "TestPass9"
EMPLOYEE_EMAIL = "test_employee@example.test"


def _create_route_tables(engine) -> None:
    from tests.unit.engineer_fixtures import create_route_tables as _create_tables

    _create_tables(
        engine,
        include_project=True,
        include_allocation=True,
        include_config=True,
    )


def _set_login_password(session: Session, *, username: str, password: str) -> None:
    model = session.scalar(select(UserModel).where(UserModel.username == username))
    assert model is not None
    model.password_hash = BcryptPasswordHasher().hash(password)
    model.force_password_change = False


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    engine = create_sqlite_engine()
    _create_route_tables(engine)

    with Session(engine) as setup:
        seed_bootstrap_admin(
            setup,
            username=TEST_USERNAME,
            password=TEST_PASSWORD,
            full_name=TEST_FULL_NAME,
            email=TEST_EMAIL,
        )
        mark_user_onboarded(setup, username=TEST_USERNAME, password=TEST_PASSWORD)
        seed_default_system_configuration(setup)
        manager_id = create_user(
            setup,
            full_name="Test Manager",
            username=MANAGER_USERNAME,
            email=MANAGER_EMAIL,
            role=Role.MANAGER,
            department_name="Delivery",
            designation_name="Project Manager",
        )
        user_id = create_user(
            setup,
            full_name="Ravi Kumar",
            username=EMPLOYEE_USERNAME,
            email=EMPLOYEE_EMAIL,
            role=Role.ENGINEER,
            manager_id=manager_id,
        )
        _set_login_password(setup, username=MANAGER_USERNAME, password=MANAGER_PASSWORD)
        project = ProjectModel(
            name="Alpha Portal",
            description="Test project",
            start_date=date(2026, 3, 1),
            end_date=date(2026, 6, 30),
            manager_user_id=manager_id,
        )
        setup.add(project)
        setup.flush()
        setup.add(
            AllocationModel(
                user_id=user_id,
                project_id=project.id,
                utilisation_percent=50,
                from_date=date(2026, 3, 1),
                to_date=date(2026, 6, 30),
                status=AllocationStatus.ACTIVE,
                created_by_user_id=manager_id,
            )
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
    assert row["user_full_name"] == "Ravi Kumar"
    assert row["project_name"] == "Alpha Portal"
    assert row["utilisation_percent"] == 50


def test_list_allocations_filters_by_user_id(client: TestClient) -> None:
    listing = client.get("/admin/allocations", headers=_admin_headers(client)).json()
    user_id = listing["allocations"][0]["user_id"]

    response = client.get(
        f"/admin/allocations?user_id={user_id}",
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
