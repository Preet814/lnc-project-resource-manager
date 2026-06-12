"""Smoke tests for manager resource dashboard and allocation against a running API."""

import uuid

import pytest

from tests.integration.support import (
    admin_headers as _admin_headers,
)
from tests.integration.support import (
    api_url as _api_url,
)
from tests.integration.support import (
    request_or_skip as _request_or_skip,
)

TEMP_PASSWORD = "TempPass1"


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
def test_manager_resource_dashboard_and_allocate_smoke() -> None:
    """Manager can view dashboard, allocate directly, and end an allocation."""
    admin_headers = _admin_headers()
    prefix = uuid.uuid4().hex[:8]
    manager = _create_manager(admin_headers, prefix=f"mgr_{prefix}")
    employee = _create_employee(admin_headers, prefix=f"emp_{prefix}")
    _assign_manager(
        admin_headers,
        engineer_user_id=employee["id"],
        manager_user_id=manager["id"],
    )
    project = _create_project(
        admin_headers,
        manager_user_id=manager["id"],
        prefix=prefix,
    )
    manager_headers = _manager_headers(username=manager["username"])

    dashboard = _request_or_skip(
        "get",
        _api_url("/manager/resources"),
        headers=manager_headers,
    )
    assert dashboard.status_code == 200
    body = dashboard.json()
    assert "on_bench" in body
    assert "active" in body
    assert body["bench_count"] >= 1

    detail = _request_or_skip(
        "get",
        _api_url(f"/manager/resources/{employee['id']}"),
        headers=manager_headers,
    )
    assert detail.status_code == 200
    assert detail.json()["work_status"] == "BENCH"

    created = _request_or_skip(
        "post",
        _api_url("/manager/allocations"),
        headers=manager_headers,
        json={
            "project_id": project["id"],
            "user_id": employee["id"],
            "utilisation_percent": 50,
            "from_date": "2026-06-01",
            "to_date": "2026-09-30",
        },
    )
    assert created.status_code == 201
    allocation = created.json()
    assert allocation["status"] == "ACTIVE"
    assert allocation["utilisation_percent"] == 50

    listing = _request_or_skip(
        "get",
        _api_url(f"/manager/projects/{project['id']}/allocations"),
        headers=manager_headers,
    )
    assert listing.status_code == 200
    assert listing.json()["total"] >= 1

    ended = _request_or_skip(
        "post",
        _api_url(f"/manager/allocations/{allocation['allocation_id']}/end"),
        headers=manager_headers,
        json={"as_of": "2026-06-14"},
    )
    assert ended.status_code == 200
    assert ended.json()["status"] == "ENDED"

    detail_after = _request_or_skip(
        "get",
        _api_url(f"/manager/resources/{employee['id']}"),
        headers=manager_headers,
    )
    assert detail_after.status_code == 200
    assert detail_after.json()["work_status"] == "BENCH"
