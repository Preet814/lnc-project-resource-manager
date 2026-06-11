"""Smoke tests for admin employee and skills management against a running API."""

import uuid

import pytest

from tests.integration.support import (
    admin_headers as _admin_headers,
    api_url as _api_url,
    request_or_skip as _request_or_skip,
)

TEMP_PASSWORD = "TempPass1"


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
            "role": "ENGINEER",
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
            "designation": "SE",
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
    employee_ids = {row["id"] for row in listed["engineers"]}
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
            f"/admin/employees/{employee['id']}/skills/{added['user_skill_id']}"
        ),
        headers=headers,
        json={"proficiency": "ADVANCED"},
    )
    assert updated.status_code == 200
    assert updated.json()["proficiency"] == "ADVANCED"

    removed = _request_or_skip(
        "delete",
        _api_url(
            f"/admin/employees/{employee['id']}/skills/{added['user_skill_id']}"
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
