"""Smoke tests for auth against a running API (Docker or local server)."""

import os

import httpx
import pytest

API_BASE_URL = os.getenv("PRM_API_URL", "http://localhost:8000")
NEW_PASSWORD = "NewSecure1"


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


def _post_or_skip(url: str, **kwargs: object) -> httpx.Response:
    try:
        return httpx.post(url, timeout=10.0, **kwargs)
    except httpx.ConnectError as exc:
        pytest.skip(f"API not running at {API_BASE_URL}: {exc}")


@pytest.mark.integration
def test_auth_login_smoke() -> None:
    """Bootstrap admin can log in and receives a JWT."""
    username, password = _bootstrap_credentials()
    response = _post_or_skip(
        _api_url("/auth/login"),
        json={"username": username, "password": password},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["access_token"]
    assert body["token_type"] == "bearer"
    assert body["username"] == username
    assert "force_password_change" in body
    assert body["role"] == "ADMIN"


@pytest.mark.integration
def test_auth_forced_password_change_smoke() -> None:
    """First-login flow: change password clears force_password_change flag."""
    username, password = _bootstrap_credentials()
    login = _post_or_skip(
        _api_url("/auth/login"),
        json={"username": username, "password": password},
    )
    assert login.status_code == 200
    login_body = login.json()

    if not login_body["force_password_change"]:
        pytest.skip(
            "Bootstrap admin already changed password; reset DB/volume to re-test "
            "forced password change (docker compose down -v && up --build)"
        )

    token = login_body["access_token"]
    change = _post_or_skip(
        _api_url("/auth/change-password"),
        headers={"Authorization": f"Bearer {token}"},
        json={"new_password": NEW_PASSWORD, "confirm_password": NEW_PASSWORD},
    )
    assert change.status_code == 200
    change_body = change.json()
    assert change_body["force_password_change"] is False
    assert change_body["access_token"] != token

    relogin = _post_or_skip(
        _api_url("/auth/login"),
        json={"username": username, "password": NEW_PASSWORD},
    )
    assert relogin.status_code == 200
    assert relogin.json()["force_password_change"] is False
