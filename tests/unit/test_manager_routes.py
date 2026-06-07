"""Unit tests for manager resource dashboard and allocation HTTP endpoints."""

from collections.abc import Generator
from datetime import date

import pytest
from fastapi import Depends
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from prm.api.app import create_app
from prm.api.deps import get_resource_dashboard_service
from prm.application.resource_dashboard_service import ResourceDashboardService
from prm.domain.enums import AllocationStatus, EmployeeWorkStatus, Role
from prm.infrastructure.db.models import (
    AllocationModel,
    EmployeeModel,
    EmployeeSkillModel,
    ProjectModel,
    SkillModel,
    SystemConfigurationModel,
    UserModel,
)
from prm.infrastructure.db.repositories import (
    SqlAlchemyAllocationRepository,
    SqlAlchemyEmployeeRepository,
    SqlAlchemyEmployeeSkillRepository,
    SqlAlchemyProjectRepository,
    SqlAlchemySkillRepository,
    SqlAlchemyUserRepository,
)
from prm.infrastructure.db.seed import seed_bootstrap_admin, seed_default_system_configuration
from prm.infrastructure.db.session import get_db_session
from prm.infrastructure.security.password import BcryptPasswordHasher
from tests.unit.credentials import TEST_EMAIL, TEST_FULL_NAME, TEST_PASSWORD, TEST_USERNAME

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
        employee_id: int,
        *,
        weeks: int = 4,
        as_of: date | None = None,
    ) -> list[str]:
        return []


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
        repo.create(
            full_name="Other Manager",
            username=OTHER_MANAGER_USERNAME,
            email=OTHER_MANAGER_EMAIL,
            password_hash=hasher.hash(OTHER_MANAGER_PASSWORD),
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
        bench_user = repo.create(
            full_name="Priya Sharma",
            username=BENCH_USERNAME,
            email=BENCH_EMAIL,
            password_hash=hasher.hash(BENCH_PASSWORD),
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
        employee_repo.create(
            user_id=bench_user.id,
            full_name="Priya Sharma",
            email=BENCH_EMAIL,
            department="Frontend",
            designation="Developer",
        )
        employee_repo.update_utilisation_and_status(
            employee.id,
            current_utilisation_percent=50,
            work_status=EmployeeWorkStatus.ALLOCATED,
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

    def override_get_resource_dashboard_service(
        db: Session = Depends(get_db_session),
    ) -> ResourceDashboardService:
        return ResourceDashboardService(
            employee_repository=SqlAlchemyEmployeeRepository(db),
            employee_skill_repository=SqlAlchemyEmployeeSkillRepository(db),
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
    employee_id = listing["active"][0]["employee_id"]

    response = client.get(
        f"/manager/resources/{employee_id}",
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
    assert body["allocations"][0]["employee_full_name"] == "Ravi Kumar"


def test_create_allocation_returns_201(client: TestClient) -> None:
    dashboard = client.get("/manager/resources", headers=_manager_headers(client)).json()
    bench_employee_id = dashboard["on_bench"][0]["employee_id"]
    admin_allocations = client.get("/admin/allocations", headers=_admin_headers(client)).json()
    project_id = admin_allocations["allocations"][0]["project_id"]

    response = client.post(
        "/manager/allocations",
        headers=_manager_headers(client),
        json={
            "project_id": project_id,
            "employee_id": bench_employee_id,
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
    employee_id = dashboard["active"][0]["employee_id"]
    admin_allocations = client.get("/admin/allocations", headers=_admin_headers(client)).json()
    project_id = admin_allocations["allocations"][0]["project_id"]

    response = client.post(
        "/manager/allocations",
        headers=_manager_headers(client),
        json={
            "project_id": project_id,
            "employee_id": employee_id,
            "utilisation_percent": 75,
            "from_date": "2026-03-01",
            "to_date": "2026-06-30",
        },
    )

    assert response.status_code == 409
    assert "125%" in response.json()["detail"]


def test_create_allocation_returns_403_for_non_owner(client: TestClient) -> None:
    dashboard = client.get("/manager/resources", headers=_manager_headers(client)).json()
    bench_employee_id = dashboard["on_bench"][0]["employee_id"]
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
            "employee_id": bench_employee_id,
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
