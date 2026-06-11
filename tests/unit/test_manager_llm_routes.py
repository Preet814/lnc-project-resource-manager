"""Unit tests for manager LLM skill match and risk summary HTTP endpoints."""

from collections.abc import Generator
from datetime import UTC, date, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import JSON, create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from prm.api.app import create_app
from prm.api.deps import get_llm_client
from prm.domain.constants import AI_RISK_SUMMARY_DISCLAIMER
from prm.domain.dtos import SkillMatchResult
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
    SkillModel,
    SystemConfigurationModel,
    TimesheetEntryModel,
    TimesheetWeekModel,
    UserModel,
    UserSkillModel,
)
from prm.infrastructure.db.repositories import SqlAlchemyMilestoneRepository
from prm.infrastructure.db.seed import seed_bootstrap_admin, seed_default_system_configuration
from prm.infrastructure.db.session import get_db_session
from prm.infrastructure.llm.fake_client import FakeLlmClient
from prm.infrastructure.security.password import BcryptPasswordHasher
from tests.unit.credentials import TEST_EMAIL, TEST_FULL_NAME, TEST_PASSWORD, TEST_USERNAME
from tests.unit.engineer_fixtures import create_user, set_engineer_status

MANAGER_USERNAME = "llm_manager"
MANAGER_PASSWORD = "TestPass9"
MANAGER_EMAIL = "llm_manager@example.test"
OTHER_MANAGER_USERNAME = "other_llm_manager"
OTHER_MANAGER_PASSWORD = "TestPass9"
OTHER_MANAGER_EMAIL = "other_llm_manager@example.test"
EMPLOYEE_USERNAME = "llm_employee"
EMPLOYEE_PASSWORD = "TestPass9"
EMPLOYEE_EMAIL = "llm_employee@example.test"
BENCH_USERNAME = "llm_bench"
BENCH_PASSWORD = "TestPass9"
BENCH_EMAIL = "llm_bench@example.test"
WEEK_START = date(2026, 5, 12)


def _create_route_tables(engine) -> None:
    from tests.unit.engineer_fixtures import create_route_tables as _create_tables

    _create_tables(
        engine,
        include_project=True,
        include_allocation=True,
        include_timesheet=True,
        include_skill=True,
        include_config=True,
    )
    ProjectHealthSnapshotModel.__table__.c.risk_flags.type = JSON()
    ProjectHealthSnapshotModel.__table__.create(engine, checkfirst=True)


def _set_login_password(session: Session, *, username: str, password: str) -> None:
    model = session.scalar(select(UserModel).where(UserModel.username == username))
    assert model is not None
    model.password_hash = BcryptPasswordHasher().hash(password)
    model.force_password_change = False


def _seed_database(setup: Session) -> tuple[int, int]:
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
    bench_id = create_user(
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
            user_id=engineer_id,
            project_id=project.id,
            utilisation_percent=50,
            from_date=date(2026, 3, 1),
            to_date=date(2026, 6, 30),
            status=AllocationStatus.ACTIVE,
            created_by_user_id=manager_id,
        )
    )
    submitted_week = TimesheetWeekModel(
        user_id=engineer_id,
        week_start_date=WEEK_START,
        status=TimesheetWeekStatus.SUBMITTED,
        total_hours=4,
    )
    setup.add(submitted_week)
    setup.flush()
    setup.add(
        TimesheetEntryModel(
            timesheet_week_id=submitted_week.id,
            project_id=project.id,
            hours_worked=4,
            activity_tags=["BACKEND_API"],
        )
    )
    setup.commit()
    return project.id, bench_id


def _build_client(
    fake_llm: FakeLlmClient | None = None,
) -> Generator[TestClient, None, None]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    _create_route_tables(engine)

    with Session(engine) as setup:
        _seed_database(setup)

    def override_get_db() -> Generator[Session, None, None]:
        db = Session(engine)
        try:
            yield db
        finally:
            db.close()

    app = create_app()
    app.dependency_overrides[get_db_session] = override_get_db
    if fake_llm is not None:
        app.dependency_overrides[get_llm_client] = lambda: fake_llm

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    yield from _build_client()


@pytest.fixture
def client_with_fake_llm() -> Generator[TestClient, None, None]:
    fake_llm = FakeLlmClient(
        rank_results=(
            SkillMatchResult(
                user_id=1,
                user_name="Priya Sharma",
                reason="Strong frontend fit and fully available.",
                suggested_allocation_percent=50,
                free_hours_per_week=40,
            ),
        ),
        risk_summary="The Backend API milestone is overdue and logged hours are low.",
    )
    yield from _build_client(fake_llm)


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


def test_skill_match_returns_400_when_llm_key_not_configured(client: TestClient) -> None:
    response = client.post(
        "/manager/projects/1/skill-match",
        headers=_manager_headers(client),
        json={"requirement": "Java developer with microservices experience"},
    )

    assert response.status_code == 400
    assert "LLM API key is not configured" in response.json()["detail"]


def test_skill_match_returns_matches_with_fake_llm(client_with_fake_llm: TestClient) -> None:
    response = client_with_fake_llm.post(
        "/manager/projects/1/skill-match",
        headers=_manager_headers(client_with_fake_llm),
        json={"requirement": "React developer for a new project"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["matches"][0]["user_name"] == "Priya Sharma"
    assert body["message"] is None


def test_skill_match_returns_message_when_no_capacity(client_with_fake_llm: TestClient) -> None:
    response = client_with_fake_llm.post(
        "/manager/projects/1/skill-match",
        headers=_manager_headers(client_with_fake_llm),
        json={"requirement": "Need 50 hrs/week for backend support"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 0
    assert body["matches"] == []
    assert "50 free hours" in body["message"]


def test_skill_match_returns_403_for_non_owner(client_with_fake_llm: TestClient) -> None:
    other_token = _login_token(
        client_with_fake_llm,
        username=OTHER_MANAGER_USERNAME,
        password=OTHER_MANAGER_PASSWORD,
    )

    response = client_with_fake_llm.post(
        "/manager/projects/1/skill-match",
        headers={"Authorization": f"Bearer {other_token}"},
        json={"requirement": "Need a backend developer"},
    )

    assert response.status_code == 403


def test_risk_summary_returns_400_when_llm_key_not_configured(client: TestClient) -> None:
    response = client.get(
        "/manager/projects/1/risk-summary",
        headers=_manager_headers(client),
    )

    assert response.status_code == 400
    assert "LLM API key is not configured" in response.json()["detail"]


def test_risk_summary_returns_summary_with_fake_llm(client_with_fake_llm: TestClient) -> None:
    response = client_with_fake_llm.get(
        "/manager/projects/1/risk-summary",
        headers=_manager_headers(client_with_fake_llm),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["project_id"] == 1
    assert "overdue" in body["summary"].lower()
    assert body["disclaimer"] == AI_RISK_SUMMARY_DISCLAIMER


def test_risk_summary_returns_403_for_non_owner(client_with_fake_llm: TestClient) -> None:
    other_token = _login_token(
        client_with_fake_llm,
        username=OTHER_MANAGER_USERNAME,
        password=OTHER_MANAGER_PASSWORD,
    )

    response = client_with_fake_llm.get(
        "/manager/projects/1/risk-summary",
        headers={"Authorization": f"Bearer {other_token}"},
    )

    assert response.status_code == 403
