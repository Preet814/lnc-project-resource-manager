"""Unit tests for manager resource dashboard and allocation HTTP endpoints."""

from collections.abc import Generator
from datetime import date

import pytest
from fastapi import Depends
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from prm.api.app import create_app
from prm.api.deps import get_resource_dashboard_service
from prm.application.resource_dashboard_service import ResourceDashboardService
from prm.domain.enums import AllocationStatus, ResourceWorkStatus, Role
from prm.infrastructure.db.models import (
    AllocationModel,
    ProjectModel,
    UserModel,
)
from prm.infrastructure.db.repositories import (
    SqlAlchemyAllocationRepository,
    SqlAlchemyProjectRepository,
    SqlAlchemySkillRepository,
    SqlAlchemyUserRepository,
    SqlAlchemyUserSkillRepository,
)
from prm.infrastructure.db.seed import seed_bootstrap_admin, seed_default_system_configuration
from prm.infrastructure.db.session import get_db_session
from prm.infrastructure.security.password import BcryptPasswordHasher
from tests.unit.credentials import TEST_EMAIL, TEST_FULL_NAME, TEST_PASSWORD, TEST_USERNAME
from tests.unit.engineer_fixtures import create_user, set_engineer_status

MANAGER_USERNAME = "test_manager"
MANAGER_PASSWORD = "TestPass9"
MANAGER_EMAIL = "test_manager@example.test"
OTHER_MANAGER_USERNAME = "other_manager"
OTHER_MANAGER_PASSWORD = "TestPass9"
OTHER_MANAGER_EMAIL = "other_manager@example.test"
EMPLOYEE_USERNAME = "test_employee"
EMPLOYEE_PASSWORD = "TestPass9"
EMPLOYEE_EMAIL = "test_employee@example.test"
BENCH_USERNAME = "bench_employee"
BENCH_PASSWORD = "TestPass9"
BENCH_EMAIL = "bench_employee@example.test"


class _FakeTimesheetRepository:
    """SQLite unit tests cannot use PostgreSQL ARRAY on timesheet_entries."""

    def list_recent_activity_tags(
        self,
        user_id: int,
        *,
        weeks: int = 4,
        as_of: date | None = None,
    ) -> list[str]:
        return []


def _create_route_tables(engine) -> None:
    from tests.unit.engineer_fixtures import create_route_tables as _create_tables

    _create_tables(
        engine,
        include_project=True,
        include_allocation=True,
        include_skill=True,
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
        create_user(
            setup,
            full_name="Other Manager",
            username=OTHER_MANAGER_USERNAME,
            email=OTHER_MANAGER_EMAIL,
            role=Role.MANAGER,
            department_name="Delivery",
            designation_name="Project Manager",
        )
        engineer_id = create_user(
            setup,
            full_name="Ravi Kumar",
            username=EMPLOYEE_USERNAME,
            email=EMPLOYEE_EMAIL,
            role=Role.ENGINEER,
            manager_id=manager_id,
        )
        create_user(
            setup,
            full_name="Priya Sharma",
            username=BENCH_USERNAME,
            email=BENCH_EMAIL,
            role=Role.ENGINEER,
            manager_id=manager_id,
        )
        set_engineer_status(
            setup,
            engineer_id,
            utilisation_percent=50,
            work_status=ResourceWorkStatus.ALLOCATED,
        )
        _set_login_password(setup, username=MANAGER_USERNAME, password=MANAGER_PASSWORD)
        _set_login_password(setup, username=OTHER_MANAGER_USERNAME, password=OTHER_MANAGER_PASSWORD)
        _set_login_password(setup, username=EMPLOYEE_USERNAME, password=EMPLOYEE_PASSWORD)
        _set_login_password(setup, username=BENCH_USERNAME, password=BENCH_PASSWORD)
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
                user_id=engineer_id,
                project_id=project.id,
                utilisation_percent=50,
                from_date=date(2026, 3, 1),
                to_date=date(2026, 6, 30),
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

    def override_get_resource_dashboard_service(
        db: Session = Depends(get_db_session),
    ) -> ResourceDashboardService:
        return ResourceDashboardService(
            user_repository=SqlAlchemyUserRepository(db),
            user_skill_repository=SqlAlchemyUserSkillRepository(db),
            skill_repository=SqlAlchemySkillRepository(db),
            allocation_repository=SqlAlchemyAllocationRepository(db),
            project_repository=SqlAlchemyProjectRepository(db),
            timesheet_repository=_FakeTimesheetRepository(),
        )

    app = create_app()
    app.dependency_overrides[get_db_session] = override_get_db
    app.dependency_overrides[get_resource_dashboard_service] = (
        override_get_resource_dashboard_service
    )

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


def _manager_headers(client: TestClient) -> dict[str, str]:
    token = _login_token(client, username=MANAGER_USERNAME, password=MANAGER_PASSWORD)
    return {"Authorization": f"Bearer {token}"}


def _admin_headers(client: TestClient) -> dict[str, str]:
    token = _login_token(client, username=TEST_USERNAME, password=TEST_PASSWORD)
    return {"Authorization": f"Bearer {token}"}


def test_get_resources_requires_bearer_token(client: TestClient) -> None:
    response = client.get("/manager/resources")
    assert response.status_code == 401


def test_get_resources_returns_403_for_admin(client: TestClient) -> None:
    response = client.get("/manager/resources", headers=_admin_headers(client))
    assert response.status_code == 403


def test_get_resources_returns_dashboard(client: TestClient) -> None:
    response = client.get("/manager/resources", headers=_manager_headers(client))

    assert response.status_code == 200
    body = response.json()
    assert body["bench_count"] == 1
    assert body["on_bench"][0]["full_name"] == "Priya Sharma"
    assert len(body["active"]) == 1
    assert body["active"][0]["full_name"] == "Ravi Kumar"
    assert body["active"][0]["utilisation_percent"] == 50
    assert body["partial_count"] == 1


def test_get_employee_detail_returns_drill_down(client: TestClient) -> None:
    listing = client.get("/manager/resources", headers=_manager_headers(client)).json()
    user_id = listing["active"][0]["user_id"]

    response = client.get(
        f"/manager/resources/{user_id}",
        headers=_manager_headers(client),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["full_name"] == "Ravi Kumar"
    assert body["work_status"] == "ALLOCATED"
    assert len(body["active_allocations"]) == 1
    assert body["active_allocations"][0]["project_name"] == "Alpha Portal"


def test_list_project_allocations_returns_active_rows(client: TestClient) -> None:
    allocations = client.get("/admin/allocations", headers=_admin_headers(client)).json()
    project_id = allocations["allocations"][0]["project_id"]

    response = client.get(
        f"/manager/projects/{project_id}/allocations",
        headers=_manager_headers(client),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["allocations"][0]["user_full_name"] == "Ravi Kumar"


def test_create_allocation_returns_201(client: TestClient) -> None:
    dashboard = client.get("/manager/resources", headers=_manager_headers(client)).json()
    bench_user_id = dashboard["on_bench"][0]["user_id"]
    admin_allocations = client.get("/admin/allocations", headers=_admin_headers(client)).json()
    project_id = admin_allocations["allocations"][0]["project_id"]

    response = client.post(
        "/manager/allocations",
        headers=_manager_headers(client),
        json={
            "project_id": project_id,
            "user_id": bench_user_id,
            "utilisation_percent": 50,
            "from_date": "2026-07-01",
            "to_date": "2026-09-30",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "ACTIVE"
    assert body["utilisation_percent"] == 50


def test_create_allocation_returns_409_when_over_cap(client: TestClient) -> None:
    dashboard = client.get("/manager/resources", headers=_manager_headers(client)).json()
    user_id = dashboard["active"][0]["user_id"]
    admin_allocations = client.get("/admin/allocations", headers=_admin_headers(client)).json()
    project_id = admin_allocations["allocations"][0]["project_id"]

    response = client.post(
        "/manager/allocations",
        headers=_manager_headers(client),
        json={
            "project_id": project_id,
            "user_id": user_id,
            "utilisation_percent": 75,
            "from_date": "2026-03-01",
            "to_date": "2026-06-30",
        },
    )

    assert response.status_code == 409
    assert "125%" in response.json()["detail"]


def test_create_allocation_returns_403_for_non_owner(client: TestClient) -> None:
    dashboard = client.get("/manager/resources", headers=_manager_headers(client)).json()
    bench_user_id = dashboard["on_bench"][0]["user_id"]
    admin_allocations = client.get("/admin/allocations", headers=_admin_headers(client)).json()
    project_id = admin_allocations["allocations"][0]["project_id"]
    other_token = _login_token(
        client,
        username=OTHER_MANAGER_USERNAME,
        password=OTHER_MANAGER_PASSWORD,
    )

    response = client.post(
        "/manager/allocations",
        headers={"Authorization": f"Bearer {other_token}"},
        json={
            "project_id": project_id,
            "user_id": bench_user_id,
            "utilisation_percent": 50,
            "from_date": "2026-07-01",
            "to_date": "2026-09-30",
        },
    )

    assert response.status_code == 403


def test_end_allocation_sets_status_ended(client: TestClient) -> None:
    listing = client.get("/admin/allocations", headers=_admin_headers(client)).json()
    allocation_id = listing["allocations"][0]["allocation_id"]

    response = client.post(
        f"/manager/allocations/{allocation_id}/end",
        headers=_manager_headers(client),
        json={"as_of": "2026-06-14"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ENDED"
    assert body["to_date"] == "2026-06-14"
