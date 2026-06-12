"""Unit tests for manager team-match HTTP endpoint."""

from collections.abc import Generator
from datetime import UTC, date, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from prm.api.app import create_app
from prm.api.deps import get_llm_client
from prm.domain.dtos import TeamPlan, TeamSlotFilters, TeamSlotSpec
from prm.domain.enums import (
    ProficiencyLevel,
    ProjectHealthStatus,
    ResourceWorkStatus,
    Role,
    SkillCategory,
    TeamGapType,
)
from prm.infrastructure.db.models import ProjectModel, UserModel
from prm.infrastructure.db.repositories import (
    SqlAlchemySkillRepository,
    SqlAlchemyUserSkillRepository,
)
from prm.infrastructure.db.seed import seed_bootstrap_admin, seed_default_system_configuration
from prm.infrastructure.db.session import get_db_session
from prm.infrastructure.llm.fake_client import FakeLlmClient
from prm.infrastructure.security.password import BcryptPasswordHasher
from tests.unit.credentials import TEST_EMAIL, TEST_FULL_NAME, TEST_PASSWORD, TEST_USERNAME
from tests.unit.engineer_fixtures import create_user, set_engineer_status

MANAGER_USERNAME = "team_match_manager"
MANAGER_PASSWORD = "TestPass9"
MANAGER_EMAIL = "team_match_manager@example.test"
OTHER_MANAGER_USERNAME = "other_team_match_manager"
OTHER_MANAGER_PASSWORD = "TestPass9"
OTHER_MANAGER_EMAIL = "other_team_match_manager@example.test"
BENCH_USERNAME = "team_match_bench"
BENCH_PASSWORD = "TestPass9"
BENCH_EMAIL = "team_match_bench@example.test"


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


def _set_login_password(session: Session, *, username: str, password: str) -> None:
    model = session.scalar(select(UserModel).where(UserModel.username == username))
    assert model is not None
    model.password_hash = BcryptPasswordHasher().hash(password)
    model.force_password_change = False


def _banking_plan() -> TeamPlan:
    return TeamPlan(
        team_slots=(
            TeamSlotSpec(
                slot_id=1,
                role_label="Senior Java Developer",
                headcount=1,
                filters=TeamSlotFilters(
                    skill_category=SkillCategory.BACKEND,
                    skill_name="Java",
                    min_proficiency=ProficiencyLevel.ADVANCED,
                ),
            ),
            TeamSlotSpec(
                slot_id=2,
                role_label="QA Tester",
                headcount=1,
                filters=TeamSlotFilters(
                    skill_category=SkillCategory.QA,
                    skill_name="Selenium",
                    min_proficiency=ProficiencyLevel.INTERMEDIATE,
                ),
            ),
        ),
    )


def _seed_database(setup: Session) -> None:
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
        bench_id,
        utilisation_percent=0,
        work_status=ResourceWorkStatus.BENCH,
    )
    java_skill = SqlAlchemySkillRepository(setup).get_or_create(
        name="Java",
        category=SkillCategory.BACKEND,
    )
    SqlAlchemyUserSkillRepository(setup).assign(
        user_id=bench_id,
        skill_id=java_skill.id,
        proficiency=ProficiencyLevel.ADVANCED,
    )
    _set_login_password(setup, username=MANAGER_USERNAME, password=MANAGER_PASSWORD)
    _set_login_password(setup, username=OTHER_MANAGER_USERNAME, password=OTHER_MANAGER_PASSWORD)
    _set_login_password(setup, username=BENCH_USERNAME, password=BENCH_PASSWORD)
    setup.add(
        ProjectModel(
            name="Alpha Portal",
            description="Test project",
            start_date=date(2026, 3, 1),
            end_date=date(2026, 6, 30),
            manager_user_id=manager_id,
            health_status=ProjectHealthStatus.ON_TRACK,
            health_computed_at=datetime(2026, 5, 12, 10, 0, tzinfo=UTC),
        )
    )
    setup.commit()


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
    yield from _build_client(FakeLlmClient(team_plan=_banking_plan()))


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


def test_team_match_returns_400_when_llm_key_not_configured(client: TestClient) -> None:
    response = client.post(
        "/manager/projects/1/team-match",
        headers=_manager_headers(client),
        json={"requirement": "Need a Java developer and QA tester"},
    )

    assert response.status_code == 400
    assert "LLM API key is not configured" in response.json()["detail"]


def test_team_match_returns_assignments_and_gaps_with_fake_llm(
    client_with_fake_llm: TestClient,
) -> None:
    response = client_with_fake_llm.post(
        "/manager/projects/1/team-match",
        headers=_manager_headers(client_with_fake_llm),
        json={
            "requirement": (
                "Alpha Portal needs a Senior Java Developer and a QA Tester with Selenium"
            ),
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["project_id"] == 1
    assert "Senior Java Developer" in body["requirement"]
    assert len(body["assignments"]) == 1
    assert body["assignments"][0]["user_name"] == "Priya Sharma"
    assert "strong fit" in body["assignments"][0]["reason"]
    assert len(body["gaps"]) == 1
    assert body["gaps"][0]["gap_type"] == TeamGapType.SKILL_GAP.value
    assert "Selenium" in body["gaps"][0]["detail"]


def test_team_match_returns_403_for_non_owner(client_with_fake_llm: TestClient) -> None:
    other_token = _login_token(
        client_with_fake_llm,
        username=OTHER_MANAGER_USERNAME,
        password=OTHER_MANAGER_PASSWORD,
    )

    response = client_with_fake_llm.post(
        "/manager/projects/1/team-match",
        headers={"Authorization": f"Bearer {other_token}"},
        json={"requirement": "Need a backend developer"},
    )

    assert response.status_code == 403


def test_team_match_returns_422_for_empty_requirement(
    client_with_fake_llm: TestClient,
) -> None:
    response = client_with_fake_llm.post(
        "/manager/projects/1/team-match",
        headers=_manager_headers(client_with_fake_llm),
        json={"requirement": ""},
    )

    assert response.status_code == 422
