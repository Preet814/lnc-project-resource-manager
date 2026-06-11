"""Unit tests for manager My Projects and team timesheet HTTP endpoints."""

from collections.abc import Generator
from datetime import UTC, date, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import JSON, create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from prm.api.app import create_app
from prm.domain.enums import (
    AllocationStatus,
    MilestoneStatus,
    ProjectHealthStatus,
    ResourceWorkStatus,
    Role,
    TimesheetWeekStatus,
)
from prm.infrastructure.db.models import (
    AllocationModel,
    DepartmentModel,
    DesignationModel,
    MilestoneModel,
    ProjectHealthSnapshotModel,
    ProjectModel,
    ResourceStatusModel,
    RoleModel,
    SystemConfigurationModel,
    TimesheetEntryModel,
    TimesheetWeekModel,
    UserModel,
)
from prm.infrastructure.db.repositories import SqlAlchemyMilestoneRepository
from prm.infrastructure.db.seed import seed_bootstrap_admin, seed_default_system_configuration
from prm.infrastructure.db.session import get_db_session
from prm.infrastructure.security.password import BcryptPasswordHasher
from tests.unit.credentials import TEST_EMAIL, TEST_FULL_NAME, TEST_PASSWORD, TEST_USERNAME
from tests.unit.engineer_fixtures import create_user, set_engineer_status

MANAGER_USERNAME = "projects_manager"
MANAGER_PASSWORD = "TestPass9"
MANAGER_EMAIL = "projects_manager@example.test"
OTHER_MANAGER_USERNAME = "other_projects_manager"
OTHER_MANAGER_PASSWORD = "TestPass9"
OTHER_MANAGER_EMAIL = "other_projects_manager@example.test"
EMPLOYEE_USERNAME = "projects_employee"
EMPLOYEE_PASSWORD = "TestPass9"
EMPLOYEE_EMAIL = "projects_employee@example.test"
WEEK_START = date(2026, 5, 12)


def _create_route_tables(engine) -> None:
    from tests.unit.engineer_fixtures import create_route_tables as _create_tables

    _create_tables(
        engine,
        include_project=True,
        include_allocation=True,
        include_timesheet=True,
        include_config=True,
    )
    ProjectHealthSnapshotModel.__table__.c.risk_flags.type = JSON()
    ProjectHealthSnapshotModel.__table__.create(engine, checkfirst=True)


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
        user_id = create_user(
            setup,
            full_name="Ravi Kumar",
            username=EMPLOYEE_USERNAME,
            email=EMPLOYEE_EMAIL,
            role=Role.ENGINEER,
            manager_id=manager_id,
        )
        set_engineer_status(
            setup,
            user_id,
            utilisation_percent=50,
            work_status=ResourceWorkStatus.ALLOCATED,
        )
        _set_login_password(setup, username=MANAGER_USERNAME, password=MANAGER_PASSWORD)
        _set_login_password(setup, username=OTHER_MANAGER_USERNAME, password=OTHER_MANAGER_PASSWORD)
        _set_login_password(setup, username=EMPLOYEE_USERNAME, password=EMPLOYEE_PASSWORD)
        project = ProjectModel(
            name="Alpha Portal",
            description="Test project",
            start_date=date(2026, 3, 1),
            end_date=date(2026, 6, 30),
            manager_user_id=manager_id,
            health_status=ProjectHealthStatus.AT_RISK,
            health_computed_at=datetime(2026, 5, 12, 10, 0, tzinfo=UTC),
        )
        setup.add(project)
        setup.flush()
        SqlAlchemyMilestoneRepository(setup).create(
            project_id=project.id,
            title="Backend API",
            due_date=date(2026, 4, 15),
            status=MilestoneStatus.IN_PROGRESS,
            sequence_order=2,
        )
        setup.add(
            ProjectHealthSnapshotModel(
                project_id=project.id,
                status=ProjectHealthStatus.AT_RISK,
                risk_flags=["Backend API milestone is 5 days overdue"],
                computed_at=datetime(2026, 5, 12, 10, 0, tzinfo=UTC),
            )
        )
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
        submitted_week = TimesheetWeekModel(
            user_id=user_id,
            week_start_date=WEEK_START,
            status=TimesheetWeekStatus.SUBMITTED,
            total_hours=18,
        )
        setup.add(submitted_week)
        setup.flush()
        setup.add(
            TimesheetEntryModel(
                timesheet_week_id=submitted_week.id,
                project_id=project.id,
                hours_worked=18,
                activity_tags=["BACKEND_API"],
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


def _manager_headers(client: TestClient) -> dict[str, str]:
    token = _login_token(client, username=MANAGER_USERNAME, password=MANAGER_PASSWORD)
    return {"Authorization": f"Bearer {token}"}


def test_list_my_projects_requires_bearer_token(client: TestClient) -> None:
    response = client.get("/manager/projects")
    assert response.status_code == 401


def test_list_my_projects_returns_owned_projects(client: TestClient) -> None:
    response = client.get("/manager/projects", headers=_manager_headers(client))

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["projects"][0]["name"] == "Alpha Portal"
    assert body["projects"][0]["health_status"] == "AT_RISK"


def test_get_project_detail_returns_health_detail(client: TestClient) -> None:
    project_id = client.get("/manager/projects", headers=_manager_headers(client)).json()[
        "projects"
    ][0]["project_id"]

    response = client.get(
        f"/manager/projects/{project_id}",
        headers=_manager_headers(client),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["health_status"] == "AT_RISK"
    assert body["risk_flags"] == ["Backend API milestone is 5 days overdue"]
    assert len(body["milestones"]) == 1
    assert body["milestones"][0]["title"] == "Backend API"
    assert len(body["allocated_resources"]) == 1
    assert body["allocated_resources"][0]["user_full_name"] == "Ravi Kumar"


def test_get_project_detail_returns_403_for_non_owner(client: TestClient) -> None:
    project_id = client.get("/manager/projects", headers=_manager_headers(client)).json()[
        "projects"
    ][0]["project_id"]
    other_token = _login_token(
        client,
        username=OTHER_MANAGER_USERNAME,
        password=OTHER_MANAGER_PASSWORD,
    )

    response = client.get(
        f"/manager/projects/{project_id}",
        headers={"Authorization": f"Bearer {other_token}"},
    )

    assert response.status_code == 403


def test_list_team_timesheets_returns_submitted_row(client: TestClient) -> None:
    response = client.get(
        "/manager/timesheets",
        headers=_manager_headers(client),
        params={"week_start_date": WEEK_START.isoformat()},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["week_start_date"] == WEEK_START.isoformat()
    assert body["total"] == 1
    assert body["rows"][0]["user_full_name"] == "Ravi Kumar"
    assert body["rows"][0]["hours"] == 18
    assert body["rows"][0]["status"] == "SUBMITTED"


def test_get_employee_timesheet_detail_returns_entries(client: TestClient) -> None:
    rows = client.get(
        "/manager/timesheets",
        headers=_manager_headers(client),
        params={"week_start_date": WEEK_START.isoformat()},
    ).json()["rows"]
    user_id = rows[0]["user_id"]

    response = client.get(
        f"/manager/timesheets/{user_id}",
        headers=_manager_headers(client),
        params={"week_start_date": WEEK_START.isoformat()},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "SUBMITTED"
    assert body["total_hours"] == 18
    assert len(body["entries"]) == 1
    assert body["entries"][0]["hours_worked"] == 18


def test_get_employee_timesheet_detail_returns_404_when_employee_missing(
    client: TestClient,
) -> None:
    response = client.get(
        "/manager/timesheets/999",
        headers=_manager_headers(client),
        params={"week_start_date": WEEK_START.isoformat()},
    )

    assert response.status_code == 404
