"""Unit tests for admin project-management HTTP endpoints."""

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from prm.api.app import create_app
from prm.domain.enums import Role
from prm.infrastructure.db.models import MilestoneModel, ProjectModel, UserModel
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
    ProjectModel.__table__.create(engine, checkfirst=True)
    MilestoneModel.__table__.create(engine, checkfirst=True)

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


def _manager_user_id(client: TestClient) -> int:
    response = client.post(
        "/auth/login",
        json={"username": MANAGER_USERNAME, "password": MANAGER_PASSWORD},
    )
    assert response.status_code == 200
    return response.json()["user_id"]


def _create_user(client: TestClient, *, username: str, email: str) -> dict:
    response = client.post(
        "/admin/users",
        headers=_admin_headers(client),
        json={
            "full_name": "Route Test User",
            "email": email,
            "username": username,
            "temporary_password": "TempPass1",
            "role": "EMPLOYEE",
        },
    )
    assert response.status_code == 201
    return response.json()


def _create_project(
    client: TestClient,
    *,
    name: str = "Alpha Portal",
    manager_user_id: int | None = None,
) -> dict:
    manager_id = manager_user_id or _manager_user_id(client)
    response = client.post(
        "/admin/projects",
        headers=_admin_headers(client),
        json={
            "name": name,
            "description": "Customer portal rewrite",
            "start_date": "2026-03-01",
            "end_date": "2026-06-30",
            "status": "ACTIVE",
            "manager_user_id": manager_id,
        },
    )
    assert response.status_code == 201
    return response.json()


def test_list_projects_requires_bearer_token(client: TestClient) -> None:
    response = client.get("/admin/projects")
    assert response.status_code == 401


def test_list_projects_returns_403_for_non_admin(client: TestClient) -> None:
    token = _login_token(client, username=MANAGER_USERNAME, password=MANAGER_PASSWORD)
    response = client.get(
        "/admin/projects",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


def test_create_project_returns_201_with_health_defaults(client: TestClient) -> None:
    manager_id = _manager_user_id(client)

    response = client.post(
        "/admin/projects",
        headers=_admin_headers(client),
        json={
            "name": "Alpha Portal",
            "description": "Customer portal rewrite",
            "start_date": "2026-03-01",
            "end_date": "2026-06-30",
            "status": "ACTIVE",
            "manager_user_id": manager_id,
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Alpha Portal"
    assert body["manager_user_id"] == manager_id
    assert body["status"] == "ACTIVE"
    assert body["health_status"] == "ON_TRACK"
    assert body["health_computed_at"] is None


def test_create_project_returns_400_for_non_manager(client: TestClient) -> None:
    employee = _create_user(client, username="emp_mgr", email="emp_mgr@example.test")

    response = client.post(
        "/admin/projects",
        headers=_admin_headers(client),
        json={
            "name": "Alpha Portal",
            "description": None,
            "start_date": "2026-03-01",
            "end_date": "2026-06-30",
            "status": "ACTIVE",
            "manager_user_id": employee["id"],
        },
    )

    assert response.status_code == 400
    assert "Manager account" in response.json()["detail"]


def test_create_project_returns_400_for_invalid_dates(client: TestClient) -> None:
    manager_id = _manager_user_id(client)

    response = client.post(
        "/admin/projects",
        headers=_admin_headers(client),
        json={
            "name": "Alpha Portal",
            "description": None,
            "start_date": "2026-07-01",
            "end_date": "2026-06-30",
            "status": "ACTIVE",
            "manager_user_id": manager_id,
        },
    )

    assert response.status_code == 400
    assert "start date" in response.json()["detail"]


def test_list_projects_returns_summaries_and_counts(client: TestClient) -> None:
    _create_project(client)

    response = client.get("/admin/projects", headers=_admin_headers(client))

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["active_count"] == 1
    assert body["planned_count"] == 0
    assert body["on_hold_count"] == 0
    assert body["projects"][0]["name"] == "Alpha Portal"
    assert body["projects"][0]["manager_full_name"] == "Test Manager"


def test_get_project_returns_profile(client: TestClient) -> None:
    created = _create_project(client)

    response = client.get(
        f"/admin/projects/{created['id']}",
        headers=_admin_headers(client),
    )

    assert response.status_code == 200
    assert response.json()["id"] == created["id"]
    assert response.json()["name"] == "Alpha Portal"


def test_get_project_returns_404_for_missing(client: TestClient) -> None:
    response = client.get("/admin/projects/999", headers=_admin_headers(client))
    assert response.status_code == 404


def test_update_project_returns_updated_fields(client: TestClient) -> None:
    created = _create_project(client)

    response = client.patch(
        f"/admin/projects/{created['id']}",
        headers=_admin_headers(client),
        json={"name": "Alpha Portal v2", "status": "ON_HOLD"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Alpha Portal v2"
    assert body["status"] == "ON_HOLD"


def test_add_project_milestone_returns_201(client: TestClient) -> None:
    project = _create_project(client)

    response = client.post(
        f"/admin/projects/{project['id']}/milestones",
        headers=_admin_headers(client),
        json={
            "title": "Backend API",
            "due_date": "2026-04-15",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["title"] == "Backend API"
    assert body["status"] == "NOT_STARTED"
    assert body["sequence_order"] == 1


def test_list_project_milestones_returns_added_milestones(client: TestClient) -> None:
    project = _create_project(client)
    client.post(
        f"/admin/projects/{project['id']}/milestones",
        headers=_admin_headers(client),
        json={
            "title": "Design Complete",
            "due_date": "2026-04-01",
            "status": "DONE",
        },
    )

    response = client.get(
        f"/admin/projects/{project['id']}/milestones",
        headers=_admin_headers(client),
    )

    assert response.status_code == 200
    milestones = response.json()["milestones"]
    assert len(milestones) == 1
    assert milestones[0]["title"] == "Design Complete"
    assert milestones[0]["status"] == "DONE"


def test_update_project_milestone_returns_new_status(client: TestClient) -> None:
    project = _create_project(client)
    added = client.post(
        f"/admin/projects/{project['id']}/milestones",
        headers=_admin_headers(client),
        json={
            "title": "Backend API",
            "due_date": "2026-04-15",
        },
    ).json()

    response = client.patch(
        f"/admin/projects/{project['id']}/milestones/{added['milestone_id']}",
        headers=_admin_headers(client),
        json={"status": "IN_PROGRESS"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "IN_PROGRESS"


def test_add_project_milestone_returns_404_for_missing_project(client: TestClient) -> None:
    response = client.post(
        "/admin/projects/999/milestones",
        headers=_admin_headers(client),
        json={
            "title": "Backend API",
            "due_date": "2026-04-15",
        },
    )

    assert response.status_code == 404
