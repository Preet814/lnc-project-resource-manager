"""Role and project-owner checks (DRY for protected endpoints)."""

from prm.application.protocols import ProjectRepository
from prm.domain.entities.project import Project
from prm.domain.entities.user import User
from prm.domain.enums import Role
from prm.domain.exceptions import NotFoundError, UnauthorizedError


class AuthorizationService:
    """Centralize who may perform an action."""

    def __init__(self, project_repository: ProjectRepository | None = None) -> None:
        self._projects = project_repository

    def assert_active(self, user: User) -> None:
        if not user.is_active():
            raise UnauthorizedError("Account is inactive.")

    def assert_role(self, user: User, *allowed_roles: Role) -> None:
        if user.role not in allowed_roles:
            raise UnauthorizedError(
                f"Role {user.role.value} is not permitted for this action."
            )

    def assert_project_owner(self, manager_user_id: int, project_id: int) -> Project:
        """Only the manager who owns the project may act on its allocations (BRD §4.2)."""
        project = self._require_project(project_id)
        if not project.is_owned_by(manager_user_id):
            raise UnauthorizedError(
                "Only the project owner may manage allocations on this project."
            )
        return project

    def assert_can_allocate(self, manager_user_id: int, project_id: int) -> Project:
        """Project-owner check before creating or ending an allocation."""
        return self.assert_project_owner(manager_user_id, project_id)

    def _require_project(self, project_id: int) -> Project:
        if self._projects is None:
            raise RuntimeError("ProjectRepository is required for project ownership checks.")
        project = self._projects.find_by_id(project_id)
        if project is None:
            raise NotFoundError(f"Project {project_id} not found.")
        return project
