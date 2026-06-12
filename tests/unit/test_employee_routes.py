"""Unit tests for engineer timesheet and allocation HTTP endpoints."""

from collections.abc import Generator
from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from prm.api.app import create_app
from prm.domain.enums import AllocationStatus, Role
from prm.infrastructure.db.models import (
    AllocationModel,
    ProjectModel,
    UserModel,
)
from prm.infrastructure.db.seed import seed_bootstrap_admin, seed_default_system_configuration
from prm.infrastructure.db.session import get_db_session
from prm.infrastructure.security.password import BcryptPasswordHasher
from tests.unit.credentials import TEST_EMAIL, TEST_FULL_NAME, TEST_PASSWORD, TEST_USERNAME
from tests.unit.engineer_fixtures import create_user

MANAGER_USERNAME = "employee_routes_manager"
MANAGER_PASSWORD = "TestPass9"
MANAGER_EMAIL = "employee_routes_manager@example.test"
EMPLOYEE_USERNAME = "employee_routes_user"
EMPLOYEE_PASSWORD = "TestPass9"
EMPLOYEE_EMAIL = "employee_routes_user@example.test"
WEEK_START = date(2026, 5, 11)


def _create_route_tables(engine) -> None:
    from tests.unit.engineer_fixtures import create_route_tables as _create_tables

    _create_tables(
        engine,
        include_project=True,
        include_allocation=True,
        include_timesheet=True,
        include_config=True,
    )


def _set_login_password(session: Session, *, username: str, password: str) -> None:
    model = session.scalar(select(UserModel).where(UserModel.username == username))
    assert model is not None
    model.password_hash = BcryptPasswordHasher().hash(password)
    model.force_password_change = False


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    _create_route_tables(engine)

    with Session(engine) as setup:
        seed_bootstrap_admin(
            setup,
            username=TEST_USERNAME,
            password=TEST_PASSWORD,
            full_name=TEST_FULL_NAME,
            email=TEST_EMAIL,
        )
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
        _set_login_password(setup, username=EMPLOYEE_USERNAME, password=EMPLOYEE_PASSWORD)
        project = ProjectModel(
            name="Alpha Portal",
            description="Test project",
            start_date=date(2026, 1, 1),
            manager_user_id=manager_id,
        )
        setup.add(project)
        setup.flush()
        setup.add(
            AllocationModel(
                user_id=user_id,
                project_id=project.id,
                utilisation_percent=50,
                from_date=date(2026, 1, 1),
                to_date=date(2026, 12, 31),
                status=AllocationStatus.ACTIVE,
                created_by_user_id=manager_id,
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


def _engineer_headers(client: TestClient) -> dict[str, str]:
    token = _login_token(client, username=EMPLOYEE_USERNAME, password=EMPLOYEE_PASSWORD)
    return {"Authorization": f"Bearer {token}"}


def _manager_headers(client: TestClient) -> dict[str, str]:
    token = _login_token(client, username=MANAGER_USERNAME, password=MANAGER_PASSWORD)
    return {"Authorization": f"Bearer {token}"}


def test_submit_timesheet_requires_bearer_token(client: TestClient) -> None:
    response = client.post(
        "/engineer/timesheets",
        json={
            "week_start_date": WEEK_START.isoformat(),
            "entries": [],
        },
    )
    assert response.status_code == 401


def test_submit_timesheet_returns_403_for_manager(client: TestClient) -> None:
    response = client.post(
        "/engineer/timesheets",
        headers=_manager_headers(client),
        json={
            "week_start_date": WEEK_START.isoformat(),
            "entries": [
                {
                    "project_id": 1,
                    "hours_worked": 10,
                    "activity_tags": ["BACKEND_API"],
                }
            ],
        },
    )
    assert response.status_code == 403


def test_list_allocations_for_week_returns_expected_max_hours(client: TestClient) -> None:
    response = client.get(
        "/engineer/allocations/for-week",
        headers=_engineer_headers(client),
        params={"week_start_date": WEEK_START.isoformat()},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["week_start_date"] == WEEK_START.isoformat()
    assert body["max_weekly_hours"] == 40
    assert len(body["allocations"]) == 1
    assert body["allocations"][0]["project_name"] == "Alpha Portal"
    assert body["allocations"][0]["expected_max_hours"] == 20


def test_list_my_allocations_returns_active_rows(client: TestClient) -> None:
    response = client.get("/engineer/allocations", headers=_engineer_headers(client))

    assert response.status_code == 200
    body = response.json()
    assert body["total_utilisation_percent"] == 50
    assert len(body["allocations"]) == 1
    assert body["allocations"][0]["status"] == "ACTIVE"


def test_submit_timesheet_creates_submitted_week(client: TestClient) -> None:
    response = client.post(
        "/engineer/timesheets",
        headers=_engineer_headers(client),
        json={
            "week_start_date": WEEK_START.isoformat(),
            "entries": [
                {
                    "project_id": 1,
                    "hours_worked": 18,
                    "activity_tags": ["MICROSERVICES", "WEBSOCKET"],
                }
            ],
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "SUBMITTED"
    assert body["total_hours"] == 18
    assert body["week_start_date"] == WEEK_START.isoformat()


def test_submit_timesheet_returns_400_for_duplicate_week(client: TestClient) -> None:
    headers = _engineer_headers(client)
    payload = {
        "week_start_date": WEEK_START.isoformat(),
        "entries": [
            {
                "project_id": 1,
                "hours_worked": 10,
                "activity_tags": ["BACKEND_API"],
            }
        ],
    }
    first = client.post("/engineer/timesheets", headers=headers, json=payload)
    assert first.status_code == 201

    duplicate = client.post("/engineer/timesheets", headers=headers, json=payload)
    assert duplicate.status_code == 400
    assert "already exists" in duplicate.json()["detail"]


def test_submit_timesheet_returns_400_for_non_monday(client: TestClient) -> None:
    response = client.post(
        "/engineer/timesheets",
        headers=_engineer_headers(client),
        json={
            "week_start_date": "2026-05-12",
            "entries": [
                {
                    "project_id": 1,
                    "hours_worked": 10,
                    "activity_tags": ["BACKEND_API"],
                }
            ],
        },
    )
    assert response.status_code == 400
    assert "Monday" in response.json()["detail"]


def test_list_my_timesheets_returns_submitted_week(client: TestClient) -> None:
    headers = _engineer_headers(client)
    client.post(
        "/engineer/timesheets",
        headers=headers,
        json={
            "week_start_date": WEEK_START.isoformat(),
            "entries": [
                {
                    "project_id": 1,
                    "hours_worked": 18,
                    "activity_tags": ["MICROSERVICES"],
                }
            ],
        },
    )

    response = client.get("/engineer/timesheets", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["weeks"][0]["week_start_date"] == WEEK_START.isoformat()
    assert body["weeks"][0]["total_hours"] == 18


def test_get_my_timesheet_detail_returns_entries(client: TestClient) -> None:
    headers = _engineer_headers(client)
    client.post(
        "/engineer/timesheets",
        headers=headers,
        json={
            "week_start_date": WEEK_START.isoformat(),
            "entries": [
                {
                    "project_id": 1,
                    "hours_worked": 18,
                    "activity_tags": ["MICROSERVICES", "WEBSOCKET"],
                }
            ],
        },
    )

    response = client.get(
        f"/engineer/timesheets/{WEEK_START.isoformat()}",
        headers=headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "SUBMITTED"
    assert body["total_hours"] == 18
    assert len(body["entries"]) == 1
    assert body["entries"][0]["project_name"] == "Alpha Portal"


def test_get_my_timesheet_detail_returns_404_when_missing(client: TestClient) -> None:
    response = client.get(
        f"/engineer/timesheets/{WEEK_START.isoformat()}",
        headers=_engineer_headers(client),
    )
    assert response.status_code == 404
