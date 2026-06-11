"""Smoke tests for admin user management against a running API."""

import uuid

import pytest

from tests.integration.support import (
    admin_headers as _admin_headers,
    api_url as _api_url,
    request_or_skip as _request_or_skip,
)

TEMP_PASSWORD = "TempPass1"
RESET_PASSWORD = "ResetPass1"


def _unique_username(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


@pytest.mark.integration
def test_admin_create_and_list_users_smoke() -> None:
    """Admin can create a user and see it in the list."""
    username = _unique_username("smoke_emp")
    email = f"{username}@example.test"
    headers = _admin_headers()

    create = _request_or_skip(
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
    assert create.status_code == 201
    created = create.json()
    assert created["username"] == username
    assert created["force_password_change"] is True

    listing = _request_or_skip("get", _api_url("/admin/users"), headers=headers)
    assert listing.status_code == 200
    listed = listing.json()
    usernames = {user["username"] for user in listed["users"]}
    assert username in usernames
    assert listed["total"] >= 2
    assert listed["active_count"] >= 2


@pytest.mark.integration
def test_admin_deactivate_and_reactivate_smoke() -> None:
    """Admin can deactivate and reactivate a user account."""
    username = _unique_username("smoke_cycle")
    email = f"{username}@example.test"
    headers = _admin_headers()

    create = _request_or_skip(
        "post",
        _api_url("/admin/users"),
        headers=headers,
        json={
            "full_name": "Smoke Cycle User",
            "email": email,
            "username": username,
            "temporary_password": TEMP_PASSWORD,
            "role": "MANAGER",
        },
    )
    assert create.status_code == 201
    user_id = create.json()["id"]

    deactivate = _request_or_skip(
        "post",
        _api_url(f"/admin/users/{user_id}/deactivate"),
        headers=headers,
    )
    assert deactivate.status_code == 200
    assert deactivate.json()["account_status"] == "INACTIVE"

    reactivate = _request_or_skip(
        "post",
        _api_url(f"/admin/users/{user_id}/reactivate"),
        headers=headers,
    )
    assert reactivate.status_code == 200
    assert reactivate.json()["account_status"] == "ACTIVE"


@pytest.mark.integration
def test_admin_reset_password_smoke() -> None:
    """Admin can reset a user's password by username."""
    username = _unique_username("smoke_reset")
    email = f"{username}@example.test"
    headers = _admin_headers()

    create = _request_or_skip(
        "post",
        _api_url("/admin/users"),
        headers=headers,
        json={
            "full_name": "Smoke Reset User",
            "email": email,
            "username": username,
            "temporary_password": TEMP_PASSWORD,
            "role": "ENGINEER",
        },
    )
    assert create.status_code == 201

    reset = _request_or_skip(
        "post",
        _api_url("/admin/users/reset-password"),
        headers=headers,
        json={"identifier": username, "temporary_password": RESET_PASSWORD},
    )
    assert reset.status_code == 200
    body = reset.json()
    assert body["username"] == username
    assert body["force_password_change"] is True

    login = _request_or_skip(
        "post",
        _api_url("/auth/login"),
        json={"username": username, "password": RESET_PASSWORD},
    )
    assert login.status_code == 200
    assert login.json()["force_password_change"] is True
