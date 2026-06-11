"""Shared helpers for integration smoke tests."""

import os

import httpx
import pytest

API_BASE_URL = os.getenv("PRM_API_URL", "http://localhost:8000")
# Set by test_auth_forced_password_change_smoke; also overridable via env.
POST_PASSWORD_CHANGE = os.getenv("INTEGRATION_ADMIN_PASSWORD", "NewSecure1")


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
