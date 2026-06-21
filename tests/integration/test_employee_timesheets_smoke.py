"""Smoke tests for employee timesheet and allocation API against a running API."""

import uuid
from datetime import date, timedelta

import pytest

from tests.integration.support import (
    admin_headers as _admin_headers,
)
from tests.integration.support import (
    api_url as _api_url,
)
from tests.integration.support import (
    engineer_headers as _engineer_headers,
)
from tests.integration.support import (
    manager_headers as _manager_headers,
)
from tests.integration.support import (
    request_or_skip as _request_or_skip,
)

TEMP_PASSWORD = "TempPass1"


def _current_week_start() -> str:
    """Monday of the current ISO week (open for engineer submission)."""
    today = date.today()
    return (today - timedelta(days=today.weekday())).isoformat()


def _unique_username(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


def _create_manager(headers: dict[str, str], *, prefix: str) -> dict:
    username = _unique_username(prefix)
    email = f"{username}@example.com"
    create_user = _request_or_skip(
        "post",
        _api_url("/admin/users"),
        headers=headers,
        json={
            "full_name": "Smoke Test Manager",
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


def _create_employee_user(headers: dict[str, str], *, prefix: str) -> dict:
    username = _unique_username(prefix)
    email = f"{username}@example.com"
    create_user = _request_or_skip(
        "post",
        _api_url("/admin/users"),
        headers=headers,
        json={
            "full_name": "Smoke Test Employee",
            "email": email,
            "username": username,
            "temporary_password": TEMP_PASSWORD,
            "role": "ENGINEER",
        },
    )
    assert create_user.status_code == 201
    user = create_user.json()
    user["username"] = username
    return user


def _create_employee_profile(
    headers: dict[str, str],
    *,
    user_id: int,
    email: str,
) -> dict:
    create_employee = _request_or_skip(
        "post",
        _api_url("/admin/employees"),
        headers=headers,
        json={
            "user_id": user_id,
            "full_name": "Smoke Test Employee",
            "email": email,
            "department": "Backend",
            "designation": "SE",
        },
    )
    assert create_employee.status_code == 201
    return create_employee.json()


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
            "name": f"Smoke Project {prefix}",
            "description": "Integration smoke test project",
            "start_date": "2026-03-01",
            "end_date": "2026-12-31",
            "status": "ACTIVE",
            "manager_user_id": manager_user_id,
        },
    )
    assert create_project.status_code == 201
    return create_project.json()


@pytest.mark.integration
def test_employee_timesheets_smoke() -> None:
    """Employee can view allocations, submit a week, and read timesheet history."""
    admin_headers = _admin_headers()
    prefix = uuid.uuid4().hex[:8]
    manager = _create_manager(admin_headers, prefix=f"mgr_{prefix}")
    employee_user = _create_employee_user(admin_headers, prefix=f"emp_{prefix}")
    employee = _create_employee_profile(
        admin_headers,
        user_id=employee_user["id"],
        email=f"{employee_user['username']}@example.com",
    )
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
    week_start = _current_week_start()

    allocated = _request_or_skip(
        "post",
        _api_url("/manager/allocations"),
        headers=manager_headers,
        json={
            "project_id": project["id"],
            "user_id": employee["id"],
            "utilisation_percent": 50,
            "from_date": "2020-01-01",
            "to_date": "2030-12-31",
        },
    )
    assert allocated.status_code == 201

    for_week = _request_or_skip(
        "get",
        _api_url("/engineer/allocations/for-week"),
        headers=employee_headers,
        params={"week_start_date": week_start},
    )
    assert for_week.status_code == 200
    for_week_body = for_week.json()
    assert for_week_body["week_start_date"] == week_start
    assert for_week_body["max_weekly_hours"] >= 1
    assert len(for_week_body["allocations"]) >= 1
    allocation_row = next(
        row for row in for_week_body["allocations"] if row["project_id"] == project["id"]
    )
    hours_logged = min(18, allocation_row["expected_max_hours"])
    assert hours_logged >= 1

    submitted = _request_or_skip(
        "post",
        _api_url("/engineer/timesheets"),
        headers=employee_headers,
        json={
            "week_start_date": week_start,
            "entries": [
                {
                    "project_id": project["id"],
                    "hours_worked": hours_logged,
                    "activity_tags": ["MICROSERVICES", "WEBSOCKET"],
                }
            ],
        },
    )
    assert submitted.status_code == 201, submitted.text
    submit_body = submitted.json()
    assert submit_body["status"] == "SUBMITTED"
    assert submit_body["total_hours"] == hours_logged

    history = _request_or_skip(
        "get",
        _api_url("/engineer/timesheets"),
        headers=employee_headers,
    )
    assert history.status_code == 200
    history_body = history.json()
    assert history_body["total"] >= 1
    assert any(row["week_start_date"] == week_start for row in history_body["weeks"])

    detail = _request_or_skip(
        "get",
        _api_url(f"/engineer/timesheets/{week_start}"),
        headers=employee_headers,
    )
    assert detail.status_code == 200
    detail_body = detail.json()
    assert detail_body["status"] == "SUBMITTED"
    assert detail_body["total_hours"] == hours_logged
    assert len(detail_body["entries"]) == 1

    my_allocations = _request_or_skip(
        "get",
        _api_url("/engineer/allocations"),
        headers=employee_headers,
    )
    assert my_allocations.status_code == 200
    allocations_body = my_allocations.json()
    assert allocations_body["total_utilisation_percent"] >= 50
    assert len(allocations_body["allocations"]) >= 1

    team_timesheets = _request_or_skip(
        "get",
        _api_url("/manager/timesheets"),
        headers=manager_headers,
        params={"week_start_date": week_start},
    )
    assert team_timesheets.status_code == 200
    team_body = team_timesheets.json()
    row = next(
        item for item in team_body["rows"] if item["user_id"] == employee["id"]
    )
    assert row["status"] == "SUBMITTED"
    assert row["hours"] == hours_logged
