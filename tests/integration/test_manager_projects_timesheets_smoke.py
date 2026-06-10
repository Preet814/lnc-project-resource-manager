"""Smoke tests for manager My Projects and team timesheets against a running API."""

import os
import uuid

import httpx
import pytest

API_BASE_URL = os.getenv("PRM_API_URL", "http://localhost:8000")
TEMP_PASSWORD = "TempPass1"
WEEK_START = "2026-06-02"


def _api_url(path: str) -> str:
    return f"{API_BASE_URL.rstrip('/')}{path}"


def _bootstrap_credentials() -> tuple[str, str]:
    username = os.getenv("BOOTSTRAP_ADMIN_USERNAME", "").strip()
    password = os.getenv("BOOTSTRAP_ADMIN_PASSWORD", "").strip()
    if not username or not password:
        pytest.skip(
            "BOOTSTRAP_ADMIN_USERNAME and BOOTSTRAP_ADMIN_PASSWORD must be set "
            "(e.g. set -a && source .env && set +a)"
        )
    return username, password


def _request_or_skip(method: str, url: str, **kwargs: object) -> httpx.Response:
    try:
        request = getattr(httpx, method)
        return request(url, timeout=10.0, **kwargs)
    except httpx.ConnectError as exc:
        pytest.skip(f"API not running at {API_BASE_URL}: {exc}")


def _admin_token() -> str:
    username, password = _bootstrap_credentials()
    login = _request_or_skip(
        "post",
        _api_url("/auth/login"),
        json={"username": username, "password": password},
    )
    assert login.status_code == 200
    body = login.json()
    assert body["role"] == "ADMIN"
    return body["access_token"]


def _admin_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {_admin_token()}"}


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


def _create_employee(headers: dict[str, str], *, prefix: str) -> dict:
    username = _unique_username(prefix)
    email = f"{username}@example.test"
    create_user = _request_or_skip(
        "post",
        _api_url("/admin/users"),
        headers=headers,
        json={
            "full_name": "Smoke Test Employee",
            "email": email,
            "username": username,
            "temporary_password": TEMP_PASSWORD,
            "role": "EMPLOYEE",
        },
    )
    assert create_user.status_code == 201
    user = create_user.json()

    create_employee = _request_or_skip(
        "post",
        _api_url("/admin/employees"),
        headers=headers,
        json={
            "user_id": user["id"],
            "full_name": "Smoke Test Employee",
            "email": email,
            "department": "Backend",
            "designation": "Developer",
        },
    )
    assert create_employee.status_code == 201
    return create_employee.json()


def _assign_manager(
    headers: dict[str, str],
    *,
    employee_user_id: int,
    manager_user_id: int,
) -> None:
    assign = _request_or_skip(
        "post",
        _api_url("/admin/employees/assign-manager"),
        headers=headers,
        json={
            "employee_user_id": employee_user_id,
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


def _manager_headers(*, username: str) -> dict[str, str]:
    login = _request_or_skip(
        "post",
        _api_url("/auth/login"),
        json={"username": username, "password": TEMP_PASSWORD},
    )
    assert login.status_code == 200
    assert login.json()["role"] == "MANAGER"
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


@pytest.mark.integration
def test_manager_projects_and_timesheets_smoke() -> None:
    """Manager can list owned projects, view health detail, and read team timesheets."""
    admin_headers = _admin_headers()
    prefix = uuid.uuid4().hex[:8]
    manager = _create_manager(admin_headers, prefix=f"mgr_{prefix}")
    employee = _create_employee(admin_headers, prefix=f"emp_{prefix}")
    _assign_manager(
        admin_headers,
        employee_user_id=employee["user_id"],
        manager_user_id=manager["id"],
    )
    project = _create_project(
        admin_headers,
        manager_user_id=manager["id"],
        prefix=prefix,
    )
    manager_headers = _manager_headers(username=manager["username"])

    milestone = _request_or_skip(
        "post",
        _api_url(f"/admin/projects/{project['id']}/milestones"),
        headers=admin_headers,
        json={
            "title": "Backend API",
            "due_date": "2026-04-15",
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
            "employee_id": employee["id"],
            "utilisation_percent": 50,
            "from_date": "2026-06-01",
            "to_date": "2026-09-30",
        },
    )
    assert allocated.status_code == 201

    projects = _request_or_skip(
        "get",
        _api_url("/manager/projects"),
        headers=manager_headers,
    )
    assert projects.status_code == 200
    project_list = projects.json()
    assert project_list["total"] >= 1
    owned = next(row for row in project_list["projects"] if row["project_id"] == project["id"])
    assert owned["name"].startswith("Smoke Project")
    assert owned["health_status"] in {"ON_TRACK", "ATTENTION", "AT_RISK"}

    detail = _request_or_skip(
        "get",
        _api_url(f"/manager/projects/{project['id']}"),
        headers=manager_headers,
    )
    assert detail.status_code == 200
    detail_body = detail.json()
    assert detail_body["project_id"] == project["id"]
    assert len(detail_body["milestones"]) >= 1
    assert len(detail_body["allocated_resources"]) >= 1

    timesheets = _request_or_skip(
        "get",
        _api_url("/manager/timesheets"),
        headers=manager_headers,
        params={"week_start_date": WEEK_START},
    )
    assert timesheets.status_code == 200
    timesheet_body = timesheets.json()
    assert timesheet_body["week_start_date"] == WEEK_START
    assert timesheet_body["total"] >= 1
    row = next(
        item for item in timesheet_body["rows"] if item["employee_id"] == employee["id"]
    )
    assert row["status"] == "MISSED"
    assert row["hours"] == 0

    employee_detail = _request_or_skip(
        "get",
        _api_url(f"/manager/timesheets/{employee['id']}"),
        headers=manager_headers,
        params={"week_start_date": WEEK_START},
    )
    assert employee_detail.status_code == 200
    employee_body = employee_detail.json()
    assert employee_body["status"] == "MISSED"
    assert employee_body["total_hours"] == 0
