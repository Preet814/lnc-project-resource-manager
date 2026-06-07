"""Smoke tests for admin employee and skills management against a running API."""

import os
import uuid

import httpx
import pytest

API_BASE_URL = os.getenv("PRM_API_URL", "http://localhost:8000")
TEMP_PASSWORD = "TempPass1"


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


def _create_employee_user(headers: dict[str, str], *, prefix: str) -> dict:
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
    employee = create_employee.json()
    assert employee["work_status"] == "BENCH"
    assert employee["is_active"] is True
    return employee


@pytest.mark.integration
def test_admin_create_and_list_employees_smoke() -> None:
    """Admin can create an employee profile and see it in the list."""
    headers = _admin_headers()
    employee = _create_employee_user(headers, prefix="smoke_emp")

    listing = _request_or_skip("get", _api_url("/admin/employees"), headers=headers)
    assert listing.status_code == 200
    listed = listing.json()
    employee_ids = {row["id"] for row in listed["employees"]}
    assert employee["id"] in employee_ids
    assert listed["total"] >= 1
    assert listed["bench_count"] >= 1


@pytest.mark.integration
def test_admin_employee_skills_crud_smoke() -> None:
    """Admin can add, list, update, and remove skills on an employee."""
    headers = _admin_headers()
    employee = _create_employee_user(headers, prefix="smoke_skill")

    add = _request_or_skip(
        "post",
        _api_url(f"/admin/employees/{employee['id']}/skills"),
        headers=headers,
        json={
            "skill_name": "Docker",
            "category": "DEVOPS",
            "proficiency": "BEGINNER",
        },
    )
    assert add.status_code == 201
    added = add.json()
    assert added["skill_name"] == "Docker"

    listing = _request_or_skip(
        "get",
        _api_url(f"/admin/employees/{employee['id']}/skills"),
        headers=headers,
    )
    assert listing.status_code == 200
    assert len(listing.json()["skills"]) == 1

    updated = _request_or_skip(
        "patch",
        _api_url(
            f"/admin/employees/{employee['id']}/skills/{added['employee_skill_id']}"
        ),
        headers=headers,
        json={"proficiency": "ADVANCED"},
    )
    assert updated.status_code == 200
    assert updated.json()["proficiency"] == "ADVANCED"

    removed = _request_or_skip(
        "delete",
        _api_url(
            f"/admin/employees/{employee['id']}/skills/{added['employee_skill_id']}"
        ),
        headers=headers,
    )
    assert removed.status_code == 204

    after_remove = _request_or_skip(
        "get",
        _api_url(f"/admin/employees/{employee['id']}/skills"),
        headers=headers,
    )
    assert after_remove.status_code == 200
    assert after_remove.json()["skills"] == []


@pytest.mark.integration
def test_admin_deactivate_employee_smoke() -> None:
    """Admin can deactivate an employee profile."""
    headers = _admin_headers()
    employee = _create_employee_user(headers, prefix="smoke_deact")

    deactivate = _request_or_skip(
        "post",
        _api_url(f"/admin/employees/{employee['id']}/deactivate"),
        headers=headers,
    )
    assert deactivate.status_code == 200
    assert deactivate.json()["is_active"] is False

    get_one = _request_or_skip(
        "get",
        _api_url(f"/admin/employees/{employee['id']}"),
        headers=headers,
    )
    assert get_one.status_code == 200
    assert get_one.json()["is_active"] is False
