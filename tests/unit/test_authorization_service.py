"""Unit tests for AuthorizationService."""

from datetime import UTC, date, datetime

import pytest

from prm.application.authorization_service import AuthorizationService
from prm.domain.entities.project import Project
from prm.domain.entities.user import User
from prm.domain.enums import ProjectHealthStatus, ProjectStatus, Role, UserAccountStatus
from prm.domain.exceptions import NotFoundError, UnauthorizedError


def _user(*, role: Role = Role.ADMIN, active: bool = True, user_id: int = 1) -> User:
    now = datetime.now(UTC)
    return User(
        id=user_id,
        full_name="Test User",
        username="testuser",
        email="test@local",
        password_hash="hash",
        role=role,
        account_status=UserAccountStatus.ACTIVE if active else UserAccountStatus.INACTIVE,
        force_password_change=False,
        created_at=now,
        updated_at=now,
    )


def _project(*, project_id: int = 10, manager_user_id: int = 2) -> Project:
    return Project(
        id=project_id,
        name="Alpha Portal",
        description="Test project",
        start_date=date(2026, 1, 1),
        end_date=date(2026, 12, 31),
        status=ProjectStatus.ACTIVE,
        manager_user_id=manager_user_id,
        health_status=ProjectHealthStatus.ON_TRACK,
        health_computed_at=None,
    )


class _FakeProjectRepository:
    def __init__(self, projects: dict[int, Project]) -> None:
        self._projects = projects

    def find_by_id(self, project_id: int) -> Project | None:
        return self._projects.get(project_id)


def test_assert_active_passes_for_active_user() -> None:
    AuthorizationService().assert_active(_user())


def test_assert_active_raises_for_inactive_user() -> None:
    with pytest.raises(UnauthorizedError, match="inactive"):
        AuthorizationService().assert_active(_user(active=False))


def test_assert_role_passes_when_role_allowed() -> None:
    AuthorizationService().assert_role(_user(role=Role.MANAGER), Role.MANAGER, Role.ADMIN)


def test_assert_role_raises_when_role_not_allowed() -> None:
    with pytest.raises(UnauthorizedError, match="not permitted"):
        AuthorizationService().assert_role(_user(role=Role.EMPLOYEE), Role.ADMIN)


def test_assert_project_owner_passes_for_owner() -> None:
    project = _project(manager_user_id=2)
    authz = AuthorizationService(_FakeProjectRepository({project.id: project}))

    returned = authz.assert_project_owner(2, project.id)

    assert returned.id == project.id


def test_assert_project_owner_raises_when_not_owner() -> None:
    project = _project(manager_user_id=2)
    authz = AuthorizationService(_FakeProjectRepository({project.id: project}))

    with pytest.raises(UnauthorizedError, match="project owner"):
        authz.assert_project_owner(99, project.id)


def test_assert_project_owner_raises_when_project_missing() -> None:
    authz = AuthorizationService(_FakeProjectRepository({}))

    with pytest.raises(NotFoundError, match="Project 10 not found"):
        authz.assert_project_owner(2, 10)


def test_assert_can_allocate_delegates_to_project_owner_check() -> None:
    project = _project(manager_user_id=2)
    authz = AuthorizationService(_FakeProjectRepository({project.id: project}))

    returned = authz.assert_can_allocate(2, project.id)

    assert returned.manager_user_id == 2
