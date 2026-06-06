"""Smoke tests for admin user management against a running API."""

import os
import uuid

import httpx
import pytest

API_BASE_URL = os.getenv("PRM_API_URL", "http://localhost:8000")
TEMP_PASSWORD = "TempPass1"
RESET_PASSWORD = "ResetPass1"


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
            "role": "EMPLOYEE",
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
            "role": "EMPLOYEE",
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
