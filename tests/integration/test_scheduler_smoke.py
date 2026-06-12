"""Smoke tests for background scheduler effects against a running API and database."""

import os
import uuid
from datetime import date, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from prm.scheduler.factory import create_scheduler_service
from tests.integration.support import (
    admin_headers as _admin_headers,
)
from tests.integration.support import (
    api_url as _api_url,
)
from tests.integration.support import (
    request_or_skip as _request_or_skip,
)

TEMP_PASSWORD = "TempPass1"


def _completed_week_start() -> str:
    """Monday of the most recently completed week."""
    today = date.today()
    this_monday = today - timedelta(days=today.weekday())
    return (this_monday - timedelta(days=7)).isoformat()


def _database_url() -> str:
    url = os.getenv("DATABASE_URL", "").strip()
    if not url:
        pytest.skip(
            "DATABASE_URL must be set for scheduler integration smoke "
            "(use localhost when running pytest from the host)"
        )
    return url


def _unique_username(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


def _create_manager(headers: dict[str, str], *, prefix: str) -> dict:
    username = _unique_username(prefix)
    email = f"{username}@example.test"
    create_user = _request_or_skip(
        "post",
        _api_url("/admin/users"),
        headers=headers,
        json={
            "full_name": "Scheduler Smoke Manager",
            "email": email,
            "username": username,
            "temporary_password": TEMP_PASSWORD,
            "role": "MANAGER",
        },
    )
    assert create_user.status_code == 201
    user = create_user.json()
    user["username"] = username
    return user


def _create_employee(headers: dict[str, str], *, prefix: str) -> tuple[dict, dict]:
    username = _unique_username(prefix)
    email = f"{username}@example.test"
    create_user = _request_or_skip(
        "post",
        _api_url("/admin/users"),
        headers=headers,
        json={
            "full_name": "Scheduler Smoke Employee",
            "email": email,
            "username": username,
            "temporary_password": TEMP_PASSWORD,
            "role": "ENGINEER",
        },
    )
    assert create_user.status_code == 201
    user = create_user.json()
    user["username"] = username

    create_employee = _request_or_skip(
        "post",
        _api_url("/admin/employees"),
        headers=headers,
        json={
            "user_id": user["id"],
            "full_name": "Scheduler Smoke Employee",
            "email": email,
            "department": "Backend",
            "designation": "SE",
        },
    )
    assert create_employee.status_code == 201
    return user, create_employee.json()


def _assign_manager(
    headers: dict[str, str],
    *,
    engineer_user_id: int,
    manager_user_id: int,
) -> None:
    assign = _request_or_skip(
        "post",
        _api_url("/admin/employees/assign-manager"),
        headers=headers,
        json={
            "engineer_user_id": engineer_user_id,
            "manager_user_id": manager_user_id,
        },
    )
    assert assign.status_code == 200


def _create_project(headers: dict[str, str], *, manager_user_id: int, prefix: str) -> dict:
    create_project = _request_or_skip(
        "post",
        _api_url("/admin/projects"),
        headers=headers,
        json={
            "name": f"Scheduler Smoke Project {prefix}",
            "description": "Scheduler integration smoke test project",
            "start_date": "2026-01-01",
            "end_date": "2026-12-31",
            "status": "ACTIVE",
            "manager_user_id": manager_user_id,
        },
    )
    assert create_project.status_code == 201
    return create_project.json()


def _manager_headers(*, username: str) -> dict[str, str]:
    login = _request_or_skip(
        "post",
        _api_url("/auth/login"),
        json={"username": username, "password": TEMP_PASSWORD},
    )
    assert login.status_code == 200
    assert login.json()["role"] == "MANAGER"
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


def _engineer_headers(*, username: str) -> dict[str, str]:
    login = _request_or_skip(
        "post",
        _api_url("/auth/login"),
        json={"username": username, "password": TEMP_PASSWORD},
    )
    assert login.status_code == 200
    assert login.json()["role"] == "ENGINEER"
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


def _run_scheduler_once() -> None:
    try:
        engine = create_engine(_database_url(), pool_pre_ping=True)
        with Session(engine) as session:
            create_scheduler_service(session).run_all_jobs()
            session.commit()
    except SQLAlchemyError as exc:
        pytest.skip(f"Cannot run scheduler against database: {exc}")


@pytest.mark.integration
def test_api_health_with_scheduler_enabled_smoke() -> None:
    """API stays healthy when the background scheduler is wired into lifespan."""
    response = _request_or_skip("get", _api_url("/health"))
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


@pytest.mark.integration
def test_scheduler_updates_health_and_missed_timesheets_smoke() -> None:
    """Scheduler tick persists project health and MISSED employee timesheet weeks."""
    admin_headers = _admin_headers()
    prefix = uuid.uuid4().hex[:8]
    manager = _create_manager(admin_headers, prefix=f"mgr_{prefix}")
    employee_user, employee = _create_employee(admin_headers, prefix=f"emp_{prefix}")
    _assign_manager(
        admin_headers,
        engineer_user_id=employee_user["id"],
        manager_user_id=manager["id"],
    )
    project = _create_project(
        admin_headers,
        manager_user_id=manager["id"],
        prefix=prefix,
    )
    manager_headers = _manager_headers(username=manager["username"])
    employee_headers = _engineer_headers(username=employee_user["username"])
    missed_week = _completed_week_start()

    milestone = _request_or_skip(
        "post",
        _api_url(f"/admin/projects/{project['id']}/milestones"),
        headers=admin_headers,
        json={
            "title": "Backend API",
            "due_date": "2026-04-01",
            "status": "IN_PROGRESS",
            "sequence_order": 1,
        },
    )
    assert milestone.status_code == 201

    allocated = _request_or_skip(
        "post",
        _api_url("/manager/allocations"),
        headers=manager_headers,
        json={
            "project_id": project["id"],
            "user_id": employee["id"],
            "utilisation_percent": 50,
            "from_date": "2026-01-01",
            "to_date": "2026-12-31",
        },
    )
    assert allocated.status_code == 201

    _run_scheduler_once()

    detail = _request_or_skip(
        "get",
        _api_url(f"/manager/projects/{project['id']}"),
        headers=manager_headers,
    )
    assert detail.status_code == 200
    detail_body = detail.json()
    assert detail_body["health_status"] == "AT_RISK"
    assert detail_body["health_computed_at"] is not None
    assert any("overdue" in flag.lower() for flag in detail_body["risk_flags"])

    history = _request_or_skip(
        "get",
        _api_url("/engineer/timesheets"),
        headers=employee_headers,
    )
    assert history.status_code == 200
    weeks = history.json()["weeks"]
    missed = next(
        (row for row in weeks if row["week_start_date"] == missed_week),
        None,
    )
    assert missed is not None
    assert missed["status"] == "MISSED"
    assert missed["total_hours"] == 0
