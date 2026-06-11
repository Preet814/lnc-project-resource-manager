"""Manager My Projects and project health detail use cases (BRD §4.3)."""

from datetime import date

from prm.application.authorization_service import AuthorizationService
from prm.application.protocols import (
    AllocationRepository,
    MilestoneRepository,
    ProjectHealthSnapshotRepository,
    ProjectRepository,
    UserRepository,
)
from prm.domain.dtos import (
    ManagerProjectDetail,
    ManagerProjectListResult,
    ManagerProjectMilestoneRow,
    ManagerProjectResourceRow,
    ManagerProjectSummary,
)


class ManagerProjectService:
    """List owned projects and read project health detail for managers."""

    def __init__(
        self,
        project_repository: ProjectRepository,
        milestone_repository: MilestoneRepository,
        allocation_repository: AllocationRepository,
        user_repository: UserRepository,
        health_snapshot_repository: ProjectHealthSnapshotRepository,
        authorization: AuthorizationService,
    ) -> None:
        self._projects = project_repository
        self._milestones = milestone_repository
        self._allocations = allocation_repository
        self._users = user_repository
        self._health_snapshots = health_snapshot_repository
        self._authorization = authorization

    def list_my_projects(self, manager_user_id: int) -> ManagerProjectListResult:
        projects = self._projects.list_by_manager_user_id(manager_user_id)
        summaries = tuple(
            ManagerProjectSummary(
                project_id=project.id,
                name=project.name,
                end_date=project.end_date,
                health_status=project.health_status,
            )
            for project in projects
        )
        return ManagerProjectListResult(projects=summaries, total=len(summaries))

    def get_project_detail(
        self,
        manager_user_id: int,
        project_id: int,
        *,
        as_of: date | None = None,
    ) -> ManagerProjectDetail:
        project = self._authorization.assert_project_owner(manager_user_id, project_id)
        reference = as_of or date.today()
        snapshot = self._health_snapshots.find_latest_for_project(project_id)
        risk_flags = snapshot.risk_flags if snapshot is not None else ()

        milestones = self._milestones.list_for_project(project_id)
        milestone_rows = tuple(
            ManagerProjectMilestoneRow(
                milestone_id=milestone.id,
                title=milestone.title,
                due_date=milestone.due_date,
                status=milestone.status,
                sequence_order=milestone.sequence_order,
                is_overdue=milestone.is_overdue(reference),
            )
            for milestone in sorted(milestones, key=lambda row: row.sequence_order)
        )

        allocations = self._allocations.list_active(project_id=project_id)
        resource_rows = tuple(
            ManagerProjectResourceRow(
                user_id=allocation.user_id,
                user_full_name=self._user_name(allocation.user_id),
                utilisation_percent=allocation.utilisation_percent,
                from_date=allocation.from_date,
                to_date=allocation.to_date,
            )
            for allocation in allocations
        )

        return ManagerProjectDetail(
            project_id=project.id,
            name=project.name,
            health_status=project.health_status,
            health_computed_at=project.health_computed_at,
            risk_flags=risk_flags,
            milestones=milestone_rows,
            allocated_resources=resource_rows,
        )

    def _user_name(self, user_id: int) -> str:
        user = self._users.find_by_id(user_id)
        if user is None:
            return "Unknown"
        return user.full_name
