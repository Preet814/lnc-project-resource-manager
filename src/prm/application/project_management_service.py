"""Admin project-management use cases (BRD §3.2)."""

from datetime import date

from prm.application.protocols import ProjectRepository, UserRepository
from prm.domain.dtos import ProjectListResult, ProjectSummary
from prm.domain.entities.project import Project
from prm.domain.entities.user import User
from prm.domain.enums import ProjectStatus, Role
from prm.domain.exceptions import NotFoundError, ValidationError


class ProjectManagementService:
    """Create, list, get, and update projects."""

    def __init__(
        self,
        project_repository: ProjectRepository,
        user_repository: UserRepository,
    ) -> None:
        self._projects = project_repository
        self._users = user_repository

    def create_project(
        self,
        *,
        name: str,
        description: str | None,
        start_date: date,
        end_date: date | None,
        status: ProjectStatus,
        manager_user_id: int,
    ) -> Project:
        cleaned_name = name.strip()
        if not cleaned_name:
            raise ValidationError("Project name is required.")

        self._require_manager_user(manager_user_id)
        self._validate_date_range(start_date, end_date)

        return self._projects.create(
            name=cleaned_name,
            description=description.strip() if description is not None else None,
            start_date=start_date,
            end_date=end_date,
            status=status,
            manager_user_id=manager_user_id,
        )

    def list_projects(
        self,
        *,
        status: ProjectStatus | None = None,
    ) -> ProjectListResult:
        projects = self._projects.list_all(status=status)
        summaries = tuple(
            ProjectSummary(
                id=project.id,
                name=project.name,
                manager_full_name=self._manager_name(project.manager_user_id),
                end_date=project.end_date,
                status=project.status,
            )
            for project in projects
        )
        active_count = sum(1 for summary in summaries if summary.status == ProjectStatus.ACTIVE)
        planned_count = sum(1 for summary in summaries if summary.status == ProjectStatus.PLANNED)
        on_hold_count = sum(1 for summary in summaries if summary.status == ProjectStatus.ON_HOLD)
        return ProjectListResult(
            projects=summaries,
            total=len(summaries),
            active_count=active_count,
            planned_count=planned_count,
            on_hold_count=on_hold_count,
        )

    def get_project(self, project_id: int) -> Project:
        return self._require_project(project_id)

    def update_project(
        self,
        project_id: int,
        *,
        name: str | None = None,
        description: str | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
        status: ProjectStatus | None = None,
        manager_user_id: int | None = None,
    ) -> Project:
        project = self._require_project(project_id)

        if name is not None:
            cleaned_name = name.strip()
            if not cleaned_name:
                raise ValidationError("Project name is required.")
            name = cleaned_name

        if manager_user_id is not None:
            self._require_manager_user(manager_user_id)

        effective_start = start_date if start_date is not None else project.start_date
        effective_end = end_date if end_date is not None else project.end_date
        self._validate_date_range(effective_start, effective_end)

        cleaned_description = description
        if description is not None:
            cleaned_description = description.strip() or None

        return self._projects.update(
            project_id,
            name=name,
            description=cleaned_description,
            start_date=start_date,
            end_date=end_date,
            status=status,
            manager_user_id=manager_user_id,
        )

    def _require_manager_user(self, manager_user_id: int) -> User:
        user = self._users.find_by_id(manager_user_id)
        if user is None:
            raise NotFoundError(f"User {manager_user_id} not found.")
        if user.role != Role.MANAGER:
            raise ValidationError("Project manager must be an active Manager account.")
        if not user.is_active():
            raise ValidationError("Project manager must be an active Manager account.")
        return user

    def _require_project(self, project_id: int) -> Project:
        project = self._projects.find_by_id(project_id)
        if project is None:
            raise NotFoundError(f"Project {project_id} not found.")
        return project

    def _manager_name(self, manager_user_id: int) -> str:
        user = self._users.find_by_id(manager_user_id)
        if user is None:
            return "Unknown"
        return user.full_name

    @staticmethod
    def _validate_date_range(start_date: date, end_date: date | None) -> None:
        if end_date is not None and start_date > end_date:
            raise ValidationError("Project start date must be on or before the end date.")
