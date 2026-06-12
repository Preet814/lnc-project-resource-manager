"""Smoke tests for admin project and milestone management against a running API."""

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
    return create_user.json()


def _create_project(headers: dict[str, str], *, manager_user_id: int, prefix: str) -> dict:
    create_project = _request_or_skip(
        "post",
        _api_url("/admin/projects"),
        headers=headers,
        json={
            "name": f"Smoke Project {prefix}",
            "description": "Integration smoke test project",
            "start_date": "2026-03-01",
            "end_date": "2026-06-30",
            "status": "ACTIVE",
            "manager_user_id": manager_user_id,
        },
    )
    assert create_project.status_code == 201
    project = create_project.json()
    assert project["status"] == "ACTIVE"
    assert project["health_status"] == "ON_TRACK"
    return project


@pytest.mark.integration
def test_admin_create_and_list_projects_smoke() -> None:
    """Admin can create a project and see it in the list."""
    headers = _admin_headers()
    manager = _create_manager(headers, prefix="smoke_mgr")
    project = _create_project(headers, manager_user_id=manager["id"], prefix="list")

    listing = _request_or_skip("get", _api_url("/admin/projects"), headers=headers)
    assert listing.status_code == 200
    listed = listing.json()
    project_ids = {row["id"] for row in listed["projects"]}
    assert project["id"] in project_ids
    assert listed["total"] >= 1
    assert listed["active_count"] >= 1


@pytest.mark.integration
def test_admin_project_milestones_crud_smoke() -> None:
    """Admin can add, list, and update milestones on a project."""
    headers = _admin_headers()
    manager = _create_manager(headers, prefix="smoke_ms_mgr")
    project = _create_project(headers, manager_user_id=manager["id"], prefix="ms")

    add = _request_or_skip(
        "post",
        _api_url(f"/admin/projects/{project['id']}/milestones"),
        headers=headers,
        json={
            "title": "Backend API",
            "due_date": "2026-04-15",
        },
    )
    assert add.status_code == 201
    added = add.json()
    assert added["title"] == "Backend API"
    assert added["status"] == "NOT_STARTED"

    listing = _request_or_skip(
        "get",
        _api_url(f"/admin/projects/{project['id']}/milestones"),
        headers=headers,
    )
    assert listing.status_code == 200
    assert len(listing.json()["milestones"]) == 1

    updated = _request_or_skip(
        "patch",
        _api_url(
            f"/admin/projects/{project['id']}/milestones/{added['milestone_id']}"
        ),
        headers=headers,
        json={"status": "IN_PROGRESS"},
    )
    assert updated.status_code == 200
    assert updated.json()["status"] == "IN_PROGRESS"


@pytest.mark.integration
def test_admin_update_project_smoke() -> None:
    """Admin can update project details."""
    headers = _admin_headers()
    manager = _create_manager(headers, prefix="smoke_upd_mgr")
    project = _create_project(headers, manager_user_id=manager["id"], prefix="upd")

    update = _request_or_skip(
        "patch",
        _api_url(f"/admin/projects/{project['id']}"),
        headers=headers,
        json={"name": "Updated Smoke Project", "status": "ON_HOLD"},
    )
    assert update.status_code == 200
    body = update.json()
    assert body["name"] == "Updated Smoke Project"
    assert body["status"] == "ON_HOLD"

    get_one = _request_or_skip(
        "get",
        _api_url(f"/admin/projects/{project['id']}"),
        headers=headers,
    )
    assert get_one.status_code == 200
    assert get_one.json()["status"] == "ON_HOLD"
