"""Smoke tests for manager LLM skill match and risk summary against a running API."""

import uuid

import pytest

from tests.integration.support import (
    admin_headers as _admin_headers,
    api_url as _api_url,
    request_or_skip as _request_or_skip,
)

TEMP_PASSWORD = "TempPass1"


def _system_config(headers: dict[str, str]) -> dict:
    response = _request_or_skip(
        "get",
        _api_url("/admin/config"),
        headers=headers,
    )
    assert response.status_code == 200
    return response.json()


def _llm_api_key_is_configured(headers: dict[str, str]) -> bool:
    return _system_config(headers)["llm_api_key_masked"] is not None


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
    return create_employee.json()


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
def test_manager_llm_endpoints_require_api_key() -> None:
    """Skill match and risk summary return 400 when no LLM API key is configured."""
    admin_headers = _admin_headers()
    if _llm_api_key_is_configured(admin_headers):
        pytest.skip(
            "LLM API key is already configured in this environment "
            "(e.g. BOOTSTRAP_LLM_API_KEY in .env)."
        )

    prefix = uuid.uuid4().hex[:8]
    manager = _create_manager(admin_headers, prefix=f"mgr_{prefix}")
    _create_employee(admin_headers, prefix=f"emp_{prefix}")
    project = _create_project(
        admin_headers,
        manager_user_id=manager["id"],
        prefix=prefix,
    )
    manager_headers = _manager_headers(username=manager["username"])

    skill_match = _request_or_skip(
        "post",
        _api_url(f"/manager/projects/{project['id']}/skill-match"),
        headers=manager_headers,
        json={"requirement": "Need a backend developer"},
    )
    assert skill_match.status_code == 400
    assert "LLM API key is not configured" in skill_match.json()["detail"]

    risk_summary = _request_or_skip(
        "get",
        _api_url(f"/manager/projects/{project['id']}/risk-summary"),
        headers=manager_headers,
    )
    assert risk_summary.status_code == 400
    assert "LLM API key is not configured" in risk_summary.json()["detail"]


@pytest.mark.integration
def test_manager_skill_match_returns_empty_matches_without_live_llm() -> None:
    """Impossible hour requirement skips the LLM and returns an empty match list."""
    admin_headers = _admin_headers()
    if not _llm_api_key_is_configured(admin_headers):
        pytest.skip("LLM API key must be configured for skill-match endpoint wiring smoke.")

    prefix = uuid.uuid4().hex[:8]
    manager = _create_manager(admin_headers, prefix=f"mgr_{prefix}")
    _create_employee(admin_headers, prefix=f"emp_{prefix}")
    project = _create_project(
        admin_headers,
        manager_user_id=manager["id"],
        prefix=prefix,
    )
    manager_headers = _manager_headers(username=manager["username"])

    skill_match = _request_or_skip(
        "post",
        _api_url(f"/manager/projects/{project['id']}/skill-match"),
        headers=manager_headers,
        json={"requirement": "Need 500 hrs/week for backend support"},
    )
    assert skill_match.status_code == 200
    body = skill_match.json()
    assert body["total"] == 0
    assert body["matches"] == []
    assert body["message"] is not None
    assert "500 free hours" in body["message"]
