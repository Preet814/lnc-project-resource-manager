"""Integration smoke tests for BRD V4 alignment flows against a running API."""

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


def _create_manager(headers: dict[str, str], *, prefix: str) -> dict:
    username = _unique_username(prefix)
    email = f"{username}@example.test"
    create_user = _request_or_skip(
        "post",
        _api_url("/admin/users"),
        headers=headers,
        json={
            "full_name": "V4 Smoke Manager",
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
            "full_name": "V4 Smoke Employee",
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
            "full_name": "V4 Smoke Employee",
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
) -> dict:
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
    return assign.json()


def _create_project(
    headers: dict[str, str],
    *,
    manager_user_id: int,
    prefix: str,
    total_story_points: int = 0,
) -> dict:
    create_project = _request_or_skip(
        "post",
        _api_url("/admin/projects"),
        headers=headers,
        json={
            "name": f"V4 Smoke Project {prefix}",
            "description": "BRD V4 integration smoke project",
            "start_date": "2026-03-01",
            "end_date": "2026-12-31",
            "status": "ACTIVE",
            "manager_user_id": manager_user_id,
            "total_story_points": total_story_points,
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
def test_v4_admin_onboarding_and_assign_manager_smoke() -> None:
    """V4 onboarding: user account → employee profile → assign manager."""
    headers = _admin_headers()
    prefix = uuid.uuid4().hex[:8]
    manager = _create_manager(headers, prefix=f"v4_mgr_{prefix}")
    employee = _create_employee(headers, prefix=f"v4_emp_{prefix}")

    assert employee["manager_id"] is None

    assigned = _assign_manager(
        headers,
        engineer_user_id=employee["id"],
        manager_user_id=manager["id"],
    )
    assert assigned["manager_id"] == manager["id"]

    get_one = _request_or_skip(
        "get",
        _api_url(f"/admin/employees/{employee['id']}"),
        headers=headers,
    )
    assert get_one.status_code == 200
    assert get_one.json()["manager_id"] == manager["id"]


@pytest.mark.integration
def test_v4_story_points_rollups_smoke() -> None:
    """V4 story points on projects/milestones and list rollups."""
    headers = _admin_headers()
    prefix = uuid.uuid4().hex[:8]
    manager = _create_manager(headers, prefix=f"v4_sp_mgr_{prefix}")
    project = _create_project(
        headers,
        manager_user_id=manager["id"],
        prefix=prefix,
        total_story_points=100,
    )

    milestone_a = _request_or_skip(
        "post",
        _api_url(f"/admin/projects/{project['id']}/milestones"),
        headers=headers,
        json={
            "title": "Design",
            "due_date": "2026-04-01",
            "story_points": 40,
        },
    )
    assert milestone_a.status_code == 201
    milestone_b = _request_or_skip(
        "post",
        _api_url(f"/admin/projects/{project['id']}/milestones"),
        headers=headers,
        json={
            "title": "Backend",
            "due_date": "2026-05-01",
            "story_points": 60,
        },
    )
    assert milestone_b.status_code == 201

    milestone_list = _request_or_skip(
        "get",
        _api_url(f"/admin/projects/{project['id']}/milestones"),
        headers=headers,
    )
    assert milestone_list.status_code == 200
    ms_body = milestone_list.json()
    assert ms_body["total_story_points"] == 100
    assert ms_body["completed_story_points"] == 0
    assert ms_body["remaining_story_points"] == 100

    done = _request_or_skip(
        "patch",
        _api_url(
            f"/admin/projects/{project['id']}/milestones/"
            f"{milestone_a.json()['milestone_id']}"
        ),
        headers=headers,
        json={"status": "DONE"},
    )
    assert done.status_code == 200

    project_list = _request_or_skip("get", _api_url("/admin/projects"), headers=headers)
    assert project_list.status_code == 200
    summary = next(
        row for row in project_list.json()["projects"] if row["id"] == project["id"]
    )
    assert summary["story_points_done"] == 40
    assert summary["story_points_total"] == 100

    completed = _request_or_skip(
        "patch",
        _api_url(f"/admin/projects/{project['id']}"),
        headers=headers,
        json={"status": "COMPLETED"},
    )
    assert completed.status_code == 200
    assert completed.json()["status"] == "COMPLETED"

    project_list_after = _request_or_skip(
        "get", _api_url("/admin/projects"), headers=headers
    )
    assert project_list_after.status_code == 200
    listed = project_list_after.json()
    assert listed["completed_count"] >= 1


@pytest.mark.integration
def test_v4_manager_team_scoping_smoke() -> None:
    """Managers only see and allocate employees assigned to their team."""
    headers = _admin_headers()
    prefix = uuid.uuid4().hex[:8]
    manager_a = _create_manager(headers, prefix=f"v4_ma_{prefix}")
    manager_b = _create_manager(headers, prefix=f"v4_mb_{prefix}")
    employee = _create_employee(headers, prefix=f"v4_team_{prefix}")
    _assign_manager(
        headers,
        engineer_user_id=employee["id"],
        manager_user_id=manager_a["id"],
    )
    project_b = _create_project(
        headers,
        manager_user_id=manager_b["id"],
        prefix=f"b_{prefix}",
    )
    headers_b = _manager_headers(username=manager_b["username"])

    dashboard = _request_or_skip(
        "get",
        _api_url("/manager/resources"),
        headers=headers_b,
    )
    assert dashboard.status_code == 200
    visible_ids = {
        row["user_id"] for row in dashboard.json()["on_bench"]
    } | {row["user_id"] for row in dashboard.json()["active"]}
    assert employee["id"] not in visible_ids

    detail = _request_or_skip(
        "get",
        _api_url(f"/manager/resources/{employee['id']}"),
        headers=headers_b,
    )
    assert detail.status_code == 403

    blocked = _request_or_skip(
        "post",
        _api_url("/manager/allocations"),
        headers=headers_b,
        json={
            "project_id": project_b["id"],
            "user_id": employee["id"],
            "utilisation_percent": 50,
            "from_date": "2026-06-01",
            "to_date": "2026-09-30",
        },
    )
    assert blocked.status_code == 403


@pytest.mark.integration
def test_v4_completed_project_blocks_allocation_smoke() -> None:
    """COMPLETED projects reject new allocations (BRD §4.2)."""
    headers = _admin_headers()
    prefix = uuid.uuid4().hex[:8]
    manager = _create_manager(headers, prefix=f"v4_cmp_mgr_{prefix}")
    employee = _create_employee(headers, prefix=f"v4_cmp_emp_{prefix}")
    _assign_manager(
        headers,
        engineer_user_id=employee["id"],
        manager_user_id=manager["id"],
    )
    project = _create_project(
        headers,
        manager_user_id=manager["id"],
        prefix=prefix,
    )
    completed = _request_or_skip(
        "patch",
        _api_url(f"/admin/projects/{project['id']}"),
        headers=headers,
        json={"status": "COMPLETED"},
    )
    assert completed.status_code == 200

    manager_headers = _manager_headers(username=manager["username"])
    blocked = _request_or_skip(
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
    assert blocked.status_code == 400
    assert "ACTIVE or PLANNED" in blocked.json()["detail"]
