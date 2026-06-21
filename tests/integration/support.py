"""Shared helpers for integration smoke tests."""

import os

import httpx
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from prm.infrastructure.db.models.user import UserModel

API_BASE_URL = os.getenv("PRM_API_URL", "http://localhost:8000")
# Live API EmailStr rejects reserved TLDs such as .test; use example.com in smoke tests.
SMOKE_EMAIL_DOMAIN = "example.com"
SMOKE_TEMP_PASSWORD = "TempPass1"
# Set by test_auth_forced_password_change_smoke; also overridable via env.
POST_PASSWORD_CHANGE = os.getenv("INTEGRATION_ADMIN_PASSWORD", "NewSecure1")


def smoke_email(local_part: str) -> str:
    return f"{local_part}@{SMOKE_EMAIL_DOMAIN}"


def api_url(path: str) -> str:
    return f"{API_BASE_URL.rstrip('/')}{path}"


def bootstrap_credentials() -> tuple[str, str]:
    username = os.getenv("BOOTSTRAP_ADMIN_USERNAME", "").strip()
    password = os.getenv("BOOTSTRAP_ADMIN_PASSWORD", "").strip()
    if not username or not password:
        pytest.skip(
            "BOOTSTRAP_ADMIN_USERNAME and BOOTSTRAP_ADMIN_PASSWORD must be set "
            "(e.g. set -a && source .env && set +a)"
        )
    return username, password


def request_or_skip(method: str, url: str, **kwargs: object) -> httpx.Response:
    try:
        request = getattr(httpx, method)
        return request(url, timeout=10.0, **kwargs)
    except httpx.ConnectError as exc:
        pytest.skip(f"API not running at {API_BASE_URL}: {exc}")


def admin_token(*, password_candidates: tuple[str, ...] | None = None) -> str:
    """Login as bootstrap admin, trying bootstrap then post-change passwords."""
    username, bootstrap_password = bootstrap_credentials()
    candidates = password_candidates or (bootstrap_password, POST_PASSWORD_CHANGE)
    tried: set[str] = set()
    for password in candidates:
        if not password or password in tried:
            continue
        tried.add(password)
        login = request_or_skip(
            "post",
            api_url("/auth/login"),
            json={"username": username, "password": password},
        )
        if login.status_code == 200:
            body = login.json()
            assert body["role"] == "ADMIN"
            return body["access_token"]
    pytest.fail(
        "Admin login failed with bootstrap and post-change passwords. "
        "Reset DB (docker compose down -v) or align BOOTSTRAP_ADMIN_PASSWORD / "
        "INTEGRATION_ADMIN_PASSWORD with the stored admin password."
    )


def admin_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {admin_token()}"}


def _database_url() -> str:
    url = os.getenv("DATABASE_URL", "").strip()
    if not url:
        pytest.skip(
            "DATABASE_URL must be set to onboard smoke users "
            "(use localhost when running pytest from the host)"
        )
    return url


def _mark_email_verified(user_id: int) -> None:
    engine = create_engine(_database_url(), pool_pre_ping=True)
    with Session(engine) as session:
        model = session.get(UserModel, user_id)
        if model is None:
            pytest.fail(f"Smoke user {user_id} not found in database.")
        model.email_verified = True
        session.commit()


def onboard_smoke_user_headers(
    *,
    username: str,
    temporary_password: str = SMOKE_TEMP_PASSWORD,
    new_password: str | None = None,
    expected_role: str | None = None,
) -> dict[str, str]:
    """Login and complete onboarding so protected role routes accept the token."""
    resolved_new = new_password or POST_PASSWORD_CHANGE
    login = request_or_skip(
        "post",
        api_url("/auth/login"),
        json={"username": username, "password": temporary_password},
    )
    assert login.status_code == 200, login.text
    body = login.json()
    if expected_role is not None:
        assert body["role"] == expected_role
    token = body["access_token"]

    if body.get("force_password_change"):
        change = request_or_skip(
            "post",
            api_url("/auth/change-password"),
            headers={"Authorization": f"Bearer {token}"},
            json={"new_password": resolved_new, "confirm_password": resolved_new},
        )
        assert change.status_code == 200, change.text
        body = change.json()
        token = body["access_token"]

    if not body.get("email_verified"):
        _mark_email_verified(body["user_id"])
        relogin = request_or_skip(
            "post",
            api_url("/auth/login"),
            json={"username": username, "password": resolved_new},
        )
        assert relogin.status_code == 200, relogin.text
        body = relogin.json()
        if expected_role is not None:
            assert body["role"] == expected_role
        token = body["access_token"]

    return {"Authorization": f"Bearer {token}"}


def manager_headers(*, username: str) -> dict[str, str]:
    return onboard_smoke_user_headers(username=username, expected_role="MANAGER")


def engineer_headers(*, username: str) -> dict[str, str]:
    return onboard_smoke_user_headers(username=username, expected_role="ENGINEER")
