"""Unit tests for manager team-match HTTP endpoint."""

from collections.abc import Generator
from datetime import UTC, date, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from prm.api.app import create_app
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
from prm.infrastructure.security.password import BcryptPasswordHasher
from tests.unit.credentials import TEST_EMAIL, TEST_FULL_NAME, TEST_PASSWORD, TEST_USERNAME
from tests.unit.engineer_fixtures import create_user, set_engineer_status

MANAGER_USERNAME = "team_manager"
MANAGER_PASSWORD = "TestPass9"
MANAGER_EMAIL = "team_manager@example.test"
OTHER_MANAGER_USERNAME = "other_team_manager"
OTHER_MANAGER_PASSWORD = "TestPass9"
OTHER_MANAGER_EMAIL = "other_team_manager@example.test"


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


def _assign_skill(
    session: Session,
    *,
    user_id: int,
    skill_name: str,
    proficiency: ProficiencyLevel,
    category: SkillCategory = SkillCategory.BACKEND,
) -> None:
    skill_repo = SqlAlchemySkillRepository(session)
    skill = skill_repo.get_or_create(name=skill_name, category=category)
    SqlAlchemyUserSkillRepository(session).assign(
        user_id=user_id,
        skill_id=skill.id,
        proficiency=proficiency,
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
        full_name="Team Manager",
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
    java_dev = create_user(
        setup,
        full_name="Ravi Kumar",
        username="ravi.kumar",
        email="ravi@example.test",
        role=Role.ENGINEER,
        manager_id=manager_id,
    )
    devops = create_user(
        setup,
        full_name="Karan Patel",
        username="karan.patel",
        email="karan@example.test",
        role=Role.ENGINEER,
        manager_id=manager_id,
    )
    set_engineer_status(
        setup,
        java_dev,
        utilisation_percent=0,
        work_status=ResourceWorkStatus.BENCH,
    )
    set_engineer_status(
        setup,
        devops,
        utilisation_percent=25,
        work_status=ResourceWorkStatus.ALLOCATED,
    )
    _assign_skill(
        setup,
        user_id=java_dev,
        skill_name="Java",
        proficiency=ProficiencyLevel.ADVANCED,
    )
    _assign_skill(
        setup,
        user_id=devops,
        skill_name="Docker",
        proficiency=ProficiencyLevel.ADVANCED,
        category=SkillCategory.DEVOPS,
    )
    _set_login_password(setup, username=MANAGER_USERNAME, password=MANAGER_PASSWORD)
    _set_login_password(setup, username=OTHER_MANAGER_USERNAME, password=OTHER_MANAGER_PASSWORD)
    project = ProjectModel(
        name="Banking Portal",
        description="New banking portal",
        start_date=date(2026, 3, 1),
        end_date=date(2026, 12, 31),
        manager_user_id=manager_id,
        health_status=ProjectHealthStatus.ON_TRACK,
        health_computed_at=datetime(2026, 5, 12, 10, 0, tzinfo=UTC),
    )
    setup.add(project)
    setup.commit()


def _build_client() -> Generator[TestClient, None, None]:
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

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    yield from _build_client()


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


def _team_match_payload() -> dict:
    return {
        "roles": [
            {
                "role_label": "Senior Java Developer",
                "required_skills": [
                    {"skill_name": "Java", "min_proficiency": "ADVANCED"},
                ],
            },
            {
                "role_label": "DevOps Engineer",
                "required_skills": [
                    {"skill_name": "Docker", "min_proficiency": "INTERMEDIATE"},
                ],
            },
        ],
    }


def test_team_match_returns_assignments(client: TestClient) -> None:
    response = client.post(
        "/manager/projects/1/team-match",
        headers=_manager_headers(client),
        json=_team_match_payload(),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["project_id"] == 1
    assert len(body["assignments"]) == 2
    assert body["gaps"] == []
    assigned_names = {item["user_name"] for item in body["assignments"]}
    assert assigned_names == {"Ravi Kumar", "Karan Patel"}
    role_labels = {item["role_label"] for item in body["assignments"]}
    assert role_labels == {"Senior Java Developer", "DevOps Engineer"}


def test_team_match_returns_skill_gap(client: TestClient) -> None:
    response = client.post(
        "/manager/projects/1/team-match",
        headers=_manager_headers(client),
        json={
            "roles": [
                {
                    "role_label": "Selenium QA",
                    "required_skills": [
                        {"skill_name": "Selenium", "min_proficiency": "INTERMEDIATE"},
                    ],
                },
            ],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["assignments"] == []
    assert len(body["gaps"]) == 1
    assert body["gaps"][0]["gap_type"] == TeamGapType.SKILL_GAP.value
    assert "Selenium" in body["gaps"][0]["detail"]


def test_team_match_returns_403_for_non_owner(client: TestClient) -> None:
    other_token = _login_token(
        client,
        username=OTHER_MANAGER_USERNAME,
        password=OTHER_MANAGER_PASSWORD,
    )

    response = client.post(
        "/manager/projects/1/team-match",
        headers={"Authorization": f"Bearer {other_token}"},
        json=_team_match_payload(),
    )

    assert response.status_code == 403


def test_team_match_rejects_empty_roles(client: TestClient) -> None:
    response = client.post(
        "/manager/projects/1/team-match",
        headers=_manager_headers(client),
        json={"roles": []},
    )

    assert response.status_code == 422
